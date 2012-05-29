import sys, os.path
CURRENT_DIR = os.path.dirname(__file__)
sys.path.append(CURRENT_DIR)
import config
import logging
import traceback
from flask import Flask, request, session, redirect, render_template, g, flash
import render_gallery
import requests
import json
import s3deploy
import time
from optparse import OptionParser

# create our little application :)
app = Flask(__name__)
app.secret_key = 'MAKE_THIS_SOMETHING_UNIQUE'
CURRENT_DIR,filename = os.path.split(__file__)
SECTIONS = json.load(open(os.path.join(CURRENT_DIR,'sections.json')))

@app.before_request
def global_settings():
    try:
        g.settings = app.config['SETTINGS']
    except KeyError:
        try:
            g.settings = config.get_settings(request.environ['DEPLOYMENT_TARGET'])
        except:
            g.settings = config.get_settings()

    g.renderer = render_gallery.GalleryRenderer(g.settings)

@app.template_filter('propose_storylink_slug')
def propose_storylink_slug(pg_slug):
    if pg_slug.endswith('-pg'):
        pg_slug = pg_slug[:-3]
    return pg_slug + "-gallery-link"

@app.route("/")
def hello():
    env = app.create_jinja_environment()
    photo_gallery_slug = session.pop('photo_gallery_slug','')
    section = session.pop('section','')
    return render_template('front.html',photo_gallery_slug=photo_gallery_slug,section=section,sections=SECTIONS)

@app.route("/render_gallery", methods=['POST'])
def render():
    slug = request.form['photo_gallery_slug']
    section = request.form['section']
    context = dict(g.settings)
    context['section'] = section
    context['slug'] = slug
    try:
        gallery = g.renderer.fetch_and_render_gallery(slug,context=context)
        return redirect("/review/%s" % slug, 302)
    except Exception, e:
        (type, value, tb) = sys.exc_info()
        app.logger.error("%s Error rendering %s: %s" % (type,slug,value))
        for line in traceback.format_exception(type, value, tb):
            app.logger.error(line)
        flash('<span class="err-label">Error encountered:</span> %s' % str(e),"error")
        session['photo_gallery_slug'] = slug
        session['section'] = section
        return redirect('/', 302)

@app.route("/publish", methods=['post'])
def publish():
    try:
        slug = request.form['slug']
        rendered_dir = g.renderer.build_gallery_filesystem_root(slug)
        try:
            context = dict((str(k),v) for k,v in json.load(open(os.path.join(rendered_dir,"context.json"))).items())
        except:
            return "Error retrieving gallery %s from %s" % (slug, rendered_dir), 404

        s3deploy.deploy_to_s3(rendered_dir,g.settings['S3_BUCKET_NAME'])
        
        published_url = "http://%s/%s" % (context['S3_BUCKET_NAME'], slug)
        if request.form.has_key('create_storylink'):
            resp = g.renderer.create_storylink(context['gallery']['title'], published_url)
            context['storylink'] = json.loads(resp.content)['url']
        else:
            context['storylink'] = None

        for p in context['photos']:
            render_gallery.ping_fb(p['og_url'])
        render_gallery.ping_fb(published_url)
        render_gallery.ping_fb(published_url + "index.html")
        json.dump(context,open(os.path.join(rendered_dir,'context.json'),"w"),indent=2)

        return redirect("/done/%s" % slug, 302)
    except Exception, e:
        flash('<span class="err-label">Error encountered:</span> %s' % str(e),"error")
        return redirect('/review/%s' % slug,302)

@app.route("/done/<slug>", methods=['get'])
def done(slug):
    rendered_dir = g.renderer.build_gallery_filesystem_root(slug)
    try:
        context = dict((str(k),v) for k,v in json.load(open(os.path.join(rendered_dir,"context.json"))).items())
    except Exception, e:
        return "Error retrieving gallery %s from %s (%s)" % (slug, rendered_dir, e), 404
    return render_template("done.html",**context)

@app.route("/review/<slug>", methods=['get'])
def review(slug):
    """For all servers: load the rendered template in an iframe, under a 'does this look right' form  """
    if slug.endswith('/'):
        slug = slug[:-1]
    rendered_dir = g.renderer.build_gallery_filesystem_root(slug)
    try:
        context = dict((str(k),v) for k,v in json.load(open(os.path.join(rendered_dir,"context.json"))).items())
    except:
        return "Error retrieving gallery %s from %s" % (slug, rendered_dir), 404

    base_url = g.renderer.build_review_url(slug)
    rendered_url='/'.join([base_url,"index.html"])
    if not slug in context:
        context['slug'] = slug
    context['timestamp'] = time.time()
    return render_template("review.html",url=rendered_url,base_url=base_url,sections=SECTIONS,**context)

@app.route("/preview/<slug>", methods=['get'])
def preview(slug):
    """For LOCAL SERVERS: regenerate the template, recopy the assets, render as if its full screen."""
    if slug.endswith('/'):
        slug = slug[:-1]
    rendered_dir = g.renderer.build_gallery_filesystem_root(slug)
    path = os.path.join(rendered_dir,'index.html')
    if request.args.get('reload') == 'true' or not os.path.exists(path):
        g.renderer.fetch_and_render_gallery(slug)

    render_gallery.copy_assets_to(rendered_dir) # pick up CSS changes

    context = json.load(open(os.path.join(rendered_dir,'context.json')))

    context['FLASK_BASE'] = 'http://%s/static/out/%s/index.html' % (g.settings['FLASK_HOST_NAME'],slug)
    render_gallery.render_template('default',path,context)
    return open(path).read()

@app.route("/dump_settings")
def dump_settings():
    lines = []
    lines.append("<h1>Current settings</h1>")
    for k,v in g.settings.items():
        lines.append('<b>%s</b>: %s<br>' % (k,v))
    return '\n'.join(lines)



@app.errorhandler(500)
def handle_exception(error):
    logging.error(error)
    return render_template('error.html',exception=error)

@app.errorhandler(404)
def page_not_found(error):
    return 'This page does not exist', 404

def parse_args():
    parser = OptionParser()
    parser.add_option("-o", "--host", dest="host",
                      help="override the 'host' value so that one can access the local server from other machines.")
    parser.add_option("-t", "--deployment-target",
                      action="store", dest="target",
                      help="If specified, use the config settings for the given deployment target.")
    parser.add_option("-l", "--logging_level",
                      action="store", dest="logging_level",
                      help="If specified, use for the logging level.")
    (options, args) = parser.parse_args()
    return options

if __name__ == "__main__":
    opts = parse_args()
    if opts.target:
        _settings = config.get_settings(opts.target)
    else:
        _settings = config.get_settings()
    if opts.host:
        _settings['HOST'] = opts.host
        _settings['FLASK_HOST_NAME'] = "%s:5000" % opts.host
    if opts.logging_level:
        logging_level = opts.logging_level
    else:
        logging_level = _settings['LOGGING_LEVEL']
    logging.basicConfig(stream=sys.stderr,level=logging_level)
    logging.info("App.py loaded for deployment target %(DEPLOYMENT_TARGET)s" % _settings)
    app.config['SETTINGS'] = _settings
    app.run(debug=True, host=_settings['HOST'])

