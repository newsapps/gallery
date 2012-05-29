import sys, os.path
CURRENT_DIR = os.path.dirname(__file__)
sys.path.append(CURRENT_DIR)
from config import get_settings
# keep the above together -- the sys.path hack is key to locating config.settings
import requests
import json
import jinja2
import codecs
from urllib import urlencode, quote_plus
import time
import logging
import shutil
from operator import itemgetter
from dateutil.parser import parse
from dateutil.tz import gettz
from PIL import Image

import eventlet
eventlet.monkey_patch()

ASSETS_DIR=os.path.join(CURRENT_DIR,"../assets")
OUTPUT_DIR=os.path.join(CURRENT_DIR,"static/out")

EXTENSION_FOR_CONTENT_TYPE = {
    'image/jpeg': 'jpg',
}

ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(ASSETS_DIR), extensions=['jinja2.ext.i18n'])
ENV.filters['quote_plus'] = quote_plus

def format_iso(val,format_string='%b %d, %Y'):
    parsed = parse(val)
    try:
        parsed = parsed.astimezone(gettz("America/Chicago"))
    except ValueError: pass
    formatted = parsed.strftime(format_string)
    formatted = formatted.replace("May.","May") # attend to fact that May doesn't get abbreviated
    return formatted

ENV.filters['format_iso'] = format_iso

P2P_API_DOCUMENTATION="""
http://content-api.p2p.tribuneinteractive.com.stage.tribdev.com/docs/content_items
"""
"""
curl -H 'Authorization: Bearer pn_540o3o65fprmx400nw8e0vu1x_64rnrtqalfd40j50xtjtqxjm5' 'https://content-api.p2p.tribuneinteractive.com.stage.tribdev.com/current_collections/chi_news_watchdog_college_1_headlines_trb.json?include[]=items' -g
curl -H 'Authorization: Bearer 6l4tyk87sc7qjfcskxburnp9pji2bm1dn85' 'https://content-api.p2p.tribuneinteractive.com/current_collections/chi_news_watchdog_college_1_headlines_trb.json?include[]=items' -g
"""
COLLECTION_URL = "%(P2P_API_ROOT)s/current_collections/%(slug)s.json?include[]=items"
CONTENT_ITEM_URL = "%(P2P_API_ROOT)s/content_items/%(slug)s.json?include[]=related_items"
MULTI_CONTENT_URL = "%(P2P_API_ROOT)s/content_items/multi.json" # USE POST
CREATE_CONTENT_ITEM_URL = '%(P2P_API_ROOT)s/content_items.json'
FILE_UPLOAD_URL = '%(P2P_API_ROOT)s/file_uploads/upload_simple'

THUMB_WIDTH = 187
THUMB_HEIGHT = 105

IMAGE_SIZES = {
    'phone': 480,
    'tablet': 768,
    'desktop': 1024,
    'full': 1280,
}

CONCURRENCY = 10

MAX_HEIGHT_SCALE = 0.6

class GalleryRenderer(object):
    """docstring for GalleryRenderer"""
    def __init__(self, settings):
        super(GalleryRenderer, self).__init__()
        self.settings = settings

    def http_headers(self, content_type=None):
        h = {
            'Authorization': 'Bearer %(P2P_AUTH_TOKEN)s' % self.settings,
        }
        if content_type is not None:
            h['content-type'] = content_type
        return h

    def fetch_collection(self,slug):
        d = dict(self.settings)
        d['slug'] = slug
        url = COLLECTION_URL % d
        resp = requests.get(url,headers=self.http_headers())
        if not resp.ok: resp.raise_for_status()
        j = json.loads(resp.content)
        return j['collection_layout']

    def content_item_url(self, slug):
        d = dict(self.settings)
        d['slug'] = slug
        url = CONTENT_ITEM_URL % d
        return url

    def fetch_single_item(self, slug):
        url = self.content_item_url(slug)
        resp = requests.get(url,headers=self.http_headers())
        if not resp.ok: resp.raise_for_status()
        try:
            j = json.loads(resp.content)
        except ValueError:
            if resp.status_code == 404:
                raise NotFoundException(slug, url)
            raise APIException(resp)
        if j.has_key('errors'):
            logging.warn("error fetching %s" % url)
            raise Exception(j['errors'])
        return j['content_item']
    
    def fetch_gallery(self, gallery_slug):
        item = self.fetch_single_item(gallery_slug)
        photos = self.fetch_multiple_items(live_related_item_ids(item['related_items']))
        for photo in photos:
            try:
                if photo['height'] and photo['width']:
                    if not photo['thumbnail_url']:
                        photo['thumbnail_url'] = thumbnail_url(photo)
                    # we probably never want to use the auto resizer now that we're using PIL but 
                    # only turning off alt since we don't use that often
                    # if not photo['alt_thumbnail_url']:
                    #     photo['alt_thumbnail_url'] = thumbnail_url(photo,max_dimension=400)
            except: pass

        return {'gallery': item, 'photos': photos }

    def fetch_multiple_items(self, ids):                
        ids = list(ids)
        if len(ids) > 25:
            agg = []
            id_groups = segment_list(ids, 25)
            for group in id_groups:
                agg.extend(self.fetch_multiple_items(group))
            return agg

        url = MULTI_CONTENT_URL % self.settings
        items = [{'id': id} for id in ids]
        data = json.dumps({ "content_items": items })
        h = dict(self.http_headers('application/json'))
        resp = requests.post(url,data=data,headers=h)
        if not resp.ok: resp.raise_for_status()
        j = json.loads(resp.content)
        return [x['body']['content_item'] for x in j]

    def fetch_and_render_gallery(self, slug,context=None):        
        pg = self.fetch_gallery(slug)
        self.render_gallery(slug,pg,context)
        return pg

    def render_gallery(self, slug,gallery,context=None,template='default',fetch_images=True):
        logging.info("Begin rendering gallery [%s]" % slug)
        start_time = time.time()
        if context is None:
            context = dict(self.settings)

        gallery_dir = self.build_gallery_filesystem_root(slug)
        gallery['gallery']['url_root'] = self.build_s3_url(slug)


        try:
            shutil.rmtree(gallery_dir)
        except OSError: pass
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        logging.info("Copying assets to %s" % gallery_dir)
        copy_assets_to(gallery_dir)

        if fetch_images:
            logging.info("Fetching images to %s" % gallery_dir)
            fetch_gallery_images(gallery,gallery_dir)

        context.update(gallery)

        logging.info("Rendering template %s" % os.path.join(gallery_dir,'index.html'))
        render_template(template,os.path.join(gallery_dir,'index.html'),context)
        logging.info("Rendering opengraph pages")
        render_opengraph_pages(slug,gallery,gallery_dir,template)
        context['rendering_time'] = time.time() - start_time
        json.dump(context,open(os.path.join(gallery_dir,'context.json'),"w"),indent=2)
        logging.info("Finished rendering %s in %.2f seconds" % (slug, context['rendering_time']))

    def build_review_url(self, slug):
        return '%s/%s' % (self.settings['REVIEW_GALLERY_ROOT'],slug)

    def build_s3_url(self, slug):
        return "http://%s/%s" % (self.settings['S3_BUCKET_NAME'],slug)

    def build_gallery_filesystem_root(self, slug):
        return os.path.join(OUTPUT_DIR,slug)

    def create_storylink(self,title,url):
        # slug seems to get ignored...
        h = self.http_headers('application/json')
        data = { 'content_item':
            {"content_item_type_code": "storylink",
             "product_affiliate_code": "chinews",
             "source_code": "chicagotribune",
             "content_item_state_code": "live",
             "title": title,
             "url": url,
             }
        }
        resp = requests.post(CREATE_CONTENT_ITEM_URL % self.settings,data=json.dumps(data),headers=h)
        if not resp.ok:
            resp.raise_for_status()
        return resp


    def upload_image(self,flo):
        resp = requests.post(FILE_UPLOAD_URL % self.settings,files={'Filedata': flo},headers=self.http_headers())
        return resp


    def ping_fb(self,url):
        
        param = "%s?fbrefresh=CANBEANYTHING" % our_url
        fb_url = "http://developers.facebook.com/tools/debug/og/object?q=%s" % quote_plus(param)
        urlopen(fb_url)
        
            
        
class APIException(Exception):
    """docstring for APIException"""
    def __init__(self, response):
        super(APIException, self).__init__(response)
        self.response = response

class NotFoundException(Exception):
    """docstring for NotFoundException"""
    def __init__(self, slug, url):
        super(NotFoundException, self).__init__("Slug %s/url %s not found" % (slug,url))
        self.slug = slug
        self.url = url

class PhotoNotRetrieved(Exception):
    pass
        
def thumbnail_url(photo,max_dimension=187,ratio='16x9'):
    # url="http://image.p2p.tribuneinteractive.com.stage.tribdev.com/photos/preview/turbine/%(slug)s" % photo
    url="http://image.p2p.tribuneinteractive.com/photos/preview/turbine/%(slug)s" % photo
    params = {
        'namespace':'turbine',
        'size':'101279',
        'slug':photo['slug'],
        'max_dimension':str(max_dimension),
        'ratio':'16x9',
        'bust':str(time.time()),
    }
    return '?'.join([url,urlencode(params)])

def grab_and_save(url,output_dir, basename,try_harder=False):
    # get it, check its mimetype and write it to basename.extension
    if not url:
        logging.warn("no url provided to fetch %s" % basename)
        return None
    resp = requests.get(url)
    if resp.status_code == 408 and try_harder:
        logging.warn("Recieved 408 timeout for %s" % url)
        resp = requests.get(url)
    if not resp.ok: resp.raise_for_status()
    content_type = resp.headers['content-type']
    extension = None
    if content_type:
        content_type = content_type.split(';')[0]
        if not content_type.startswith('image/'):
            raise NotFoundException(basename,url)
        try:
            extension = EXTENSION_FOR_CONTENT_TYPE[content_type]
        except KeyError:
            raise Exception("Unknown content type %s for %s" % (content_type,url))
    if not extension:
        raise Exception("Content type was not specified in response.")
    basename += '.%s' % extension
    open(os.path.join(output_dir,basename),"w").write(resp.content)
    return basename

def _fetch_gallery_image(photo, gallery_dir, photos, try_harder=False):
    file_name = grab_and_save(photo['photo_services_url'],gallery_dir,photo['slug'],try_harder=try_harder)
    if file_name:
        photo['orig_name'] = file_name

        # Cut responsive images
        image = Image.open(os.path.join(gallery_dir, file_name))
        for label, max_width in IMAGE_SIZES.items():
            max_height = max_width * MAX_HEIGHT_SCALE
            if image.size[0] > max_width or image.size[1] > max_height:
                resized = image.copy()

                if image.size[0] > image.size[1]:
                    width_scale = max_width / float(resized.size[0])
                    height = int(float(resized.size[1]) * float(width_scale))
                    width = int(max_width)
                else:
                    height_scale = max_height / float(resized.size[1])
                    width = int(float(resized.size[0]) * float(height_scale))
                    height = int(max_height)

                resized = resized.resize((width, height), Image.ANTIALIAS)
                resized_name = "%s-%s" % (label, file_name)
                resized.save(os.path.join(gallery_dir,resized_name))
            else:
                resized_name = file_name

            photo["%s_url" % label] = resized_name

    # We need a 187x105 thumbnail. Ideally we can use photo['thumbnail_url']. Practically, we've seen that
    # be too small. If it's too small, we need to grab alt_thumbnail_url and scale it down.
    basename = '%s_thumb' % photo['slug']
    file_name = grab_and_save(photo['thumbnail_url'],gallery_dir,basename,try_harder=try_harder)
    if file_name:
        thumb = Image.open(os.path.join(gallery_dir, file_name))
        if thumb.size[1] == THUMB_HEIGHT:
            photo['gallery_thumbnail_url'] = file_name
        else:
            logging.warn("Given thumbnail [%s] too small for gallery thumbnail [%s x %s]" % (file_name, thumb.size[0], thumb.size[1]))
    # if we don't yet have a thumb, grab the alt and scale it down...
    if not photo.has_key('gallery_thumbnail_url') or not photo['gallery_thumbnail_url']:
        if photo['alt_thumbnail_url']:
            logging.info("No gallery thumbnail yet, grabbing alt_thumbnail_url")
            basename = '%s_alt' % photo['slug']
            file_name = grab_and_save(photo['alt_thumbnail_url'],gallery_dir,basename,try_harder=try_harder)
        else:
            logging.info("No gallery thumbnail, no alt_thumbnail, resizing main image")
            file_name = photo['orig_name']
        if file_name:
            # Resize
            thumb = Image.open(os.path.join(gallery_dir, file_name))
            resized = image.copy()
            # 
            # width_scale = THUMB_WIDTH / float(resized.size[0])
            # height = int(float(resized.size[1]) * float(width_scale))
            # resized = resized.resize((THUMB_WIDTH, height), Image.ANTIALIAS)
            # 
            height_scale = THUMB_HEIGHT / float(resized.size[1])
            width = int(float(resized.size[0]) * float(height_scale))
            resized = resized.resize((width, THUMB_HEIGHT), Image.ANTIALIAS)

            resized_name = "thumb-%s" % file_name
            resized.save(os.path.join(gallery_dir,resized_name))
            photo['gallery_thumbnail_url'] = resized_name


    photos[photo['id']] = photo

def fetch_gallery_images(gal_and_photo_dict, gallery_dir):
    """For each photo dict in the given gallery's photos, attempt to retrieve and store locally all
    relevant image files/sizes. When images have been retrieved and stored, the photo dict will be updated
    to have the filename under which the retrieved image was stored, relative to 'gallery_dir'."""

    pool = eventlet.GreenPool(CONCURRENCY)

    photos = {}
    errors = []
    def handle_error(gt,photo,errors):
        try:
            gt.wait()
        except Exception, e:
            errors.append((photo['id'],e))
        
    for i, photo in enumerate(gal_and_photo_dict['photos']):
        t = pool.spawn(_fetch_gallery_image, photo, gallery_dir, photos,try_harder=True)
        t.link(handle_error,photo,errors)
    pool.waitall()

    if errors:
        msgs = ["Problems with %i photos." % len(errors)]
        for tup in errors:
            msgs.append("Photo ID %s: %s" % tup)
        raise PhotoNotRetrieved(';'.join(msgs))

    i = 0
    for photo in gal_and_photo_dict['photos']:
        i += 1
        try:
            photo = photos[photo['id']]
        except KeyError, e:
            raise PhotoNotRetrieved("Photo %s was not retrieved." % photo['id'])
        photo['s3_photo_url'] = "%s/%s" % (gal_and_photo_dict['gallery']['url_root'],photo['orig_name'])
        photo['og_url'] = "%s/og_%s.html" % (gal_and_photo_dict['gallery']['url_root'],photo['slug'])
            
def copy_assets_to(gallery_dir):
    # can't simply use shutil.copytree because we don't want to clobber an existing directory
    if not os.path.exists(gallery_dir):
        os.makedirs(gallery_dir)
    for path,dirnames,filenames in os.walk(ASSETS_DIR):
        destpath = path.replace(ASSETS_DIR,gallery_dir)
        try: dirnames.remove('templates')
        except ValueError: pass
        for dn in dirnames:
            try: os.makedirs(os.path.join(destpath,dn))
            except OSError: pass
        for fn in filenames:
            shutil.copy(os.path.join(path,fn),os.path.join(destpath,fn))

def make_opengraph_title(photo, gallery):
    parts = [gallery['source_name'], gallery['title']]
    if photo.get('title'):
        parts.append(photo['title'])
    elif photo.get('seo_title'):
        parts.append(photo['seo_title'])
    return ' - '.join(parts)

def render_opengraph_pages(slug, gallery,gallery_dir,template='default'):
    for i,photo in enumerate(gallery['photos']):
        count = i+1
        path = os.path.join(gallery_dir,'og_%s.html' % photo['slug'])
        print path
        if photo['thumbnail_url'].startswith('http'):
            thumbnail_url = photo['thumbnail_url']
        else:
            thumbnail_url = '%s/%s' % (gallery['gallery']['url_root'], photo['thumbnail_url'])
        context = {
            'photo': photo,
            'gallery': gallery,
            'count': count,
            'title': make_opengraph_title(photo, gallery['gallery']),
            'thumbnail_url': thumbnail_url,
        }
        render_template('%s_opengraph' % template,path, context)

def render_template(template,path,context):
    kwargs = dict((str(k),v) for k,v in context.items()) # un-unicode keys
    kwargs['timestamp'] = str(time.time())
    output = ENV.get_template("templates/%s.html" % template).render(**kwargs)
    w = codecs.getwriter('utf-8')(open(path, 'w'))
    w.write(output)
    w.close()

def segment_list(l,max_len):
    segments = []
    for x in range(0,(len(l) // max_len)):
        segments.append(l[x*max_len:(x*max_len)+max_len])
    segments.append(l[(x+1)*max_len:])
    return segments

def live_related_item_ids(item_dicts):
    """Only return the ids for live items, and not the one which is not a real photo"""
    ids = []
    for ri in item_dicts:
        if ri.get('slug') != 'chi-end-photo' and ri.get(u'content_item_state_code') == 'live':
            ids.append(ri['relatedcontentitem_id'])
    return ids

def ping_fb(url,tenacious=True):
    param = "%s?fbrefresh=CANBEANYTHING" % url
    fb_url = "http://developers.facebook.com/tools/debug/og/object?q=%s" % quote_plus(param)
    resp = requests.get(fb_url)
    if not resp.ok and tenacious:
        time.sleep(2)
        ping_fb(url,False)

if __name__ == '__main__':
    settings = get_settings()
    renderer = GalleryRenderer(settings)
    for arg in sys.argv[1:]:
        renderer.fetch_and_render_gallery(arg)

