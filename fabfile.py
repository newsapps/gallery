# Chicago Tribune News Applications fabfile
# No copying allowed
from fabric.api import *

"""
Base configuration
"""
env.project_name = 'gallery'
env.path = '/home/newsapps/sites/%(project_name)s' % env
env.log_path = '/home/newsapps/logs/%(project_name)s' % env
env.env_path = '%(path)s/env' % env
env.repo_path = '%(path)s/repository' % env
env.apache_config_path = '/home/newsapps/sites/apache/%(project_name)s' % env
env.python = 'python2.6'
env.repository_url = 'git@tribune.unfuddle.com:tribune/gallery.git' % env
env.gallery_output_dir = '%(repo_path)s/app/static/out' % env

"""
Environments
"""
def production():
    """
    Work on production environment
    """
    env.settings = 'production'
#    env.hosts = ['db.tribapps.com'] 
    # deploying to staging hardware for now, while we get a handle on demand/load/etc
    env.hosts = ['db.tribapps.com'] 
    env.user = 'newsapps'
    env.s3_bucket = 'galleries.apps.chicagotribune.com'

def staging():
    """
    Work on staging environment
    """
    env.settings = 'staging'
    env.hosts = ['db.beta.tribapps.com'] 
    env.user = 'newsapps'
    env.s3_bucket = 'galleries.beta.tribapps.com'
    
"""
Branches
"""
def stable():
    """
    Work on stable branch.
    """
    env.branch = 'stable'

def master():
    """
    Work on development branch.
    """
    env.branch = 'master'

def branch(branch_name):
    """
    Work on any specified branch.
    """
    env.branch = branch_name
    
"""
Commands - setup
"""
def setup():
    """
    Setup a fresh virtualenv, install everything we need, and fire up the database.
    
    Does NOT perform the functions of deploy().
    """
    _confirm_branch()
    
    require('settings', provided_by=[production, staging])
    require('branch', provided_by=[stable, master, branch])
    
    setup_directories()
    setup_virtualenv()
    clone_repo()
    checkout_latest()
    sudo('mkdir %(gallery_output_dir)s && chgrp -R www-data %(gallery_output_dir)s && chmod -R g+w %(gallery_output_dir)s' % env)
    sudo('ln -s /usr/lib/libjpeg.so %(env_path)s/lib/libjpeg.so' % env)
    install_requirements()
    install_apache_conf()
    install_s3_website_files()

def setup_directories():
    """
    Create directories necessary for deployment.
    """
    run('mkdir -p %(path)s' % env)
    run('mkdir -p %(env_path)s' % env)
    run('mkdir -p %(log_path)s;' % env)
    sudo('chgrp -R www-data %(log_path)s; chmod -R g+w %(log_path)s;' % env)
    
    with settings(warn_only=True):
        run('ln -s %(log_path)s %(path)s/logs' % env)
    
def setup_virtualenv():
    """
    Setup a fresh virtualenv.
    """
    run('virtualenv -p %(python)s --no-site-packages %(env_path)s;' % env)
    run('source %(env_path)s/bin/activate; easy_install -U setuptools; easy_install pip;' % env)

def clone_repo():
    """
    Do initial clone of the git repository.
    """
    with settings(warn_only=True):
        run('git clone %(repository_url)s %(repo_path)s' % env)

def checkout_latest():
    """
    Pull the latest code on the specified branch.
    """
    with cd(env.repo_path):
        if env.branch != 'master':
            with settings(warn_only=True):
                run('git checkout -b %(branch)s origin/%(branch)s' % env)
        run('git checkout %(branch)s;' % env)
        run('git pull origin %(branch)s' % env)

def install_requirements():
    """
    Install the required packages using pip.
    """
    run('source %(env_path)s/bin/activate; pip install -U -r %(repo_path)s/requirements.txt' % env)

def install_apache_conf():
    """
    Install the apache site config file.
    """
    sudo('cp -T %(repo_path)s/apache/%(settings)s/apache %(apache_config_path)s' % env)

def install_s3_website_files():
    run('s3cmd -P --guess-mime-type put %(repo_path)s/apache/index.html s3://%(s3_bucket)s/' % env)
    run('s3cmd -P --guess-mime-type put %(repo_path)s/apache/error.html s3://%(s3_bucket)s/' % env)
    
"""
Commands - deployment
"""
def deploy():
    """
    Deploy the latest version of the site to the server and restart Apache2.
    
    Does not perform the functions of load_new_data().
    """
    _confirm_branch()
    
    require('settings', provided_by=[production, staging])
    require('branch', provided_by=[stable, master, branch])
    
    with settings(warn_only=True):
        maintenance_up()
        
    checkout_latest()
    # gzip_assets()
    # deploy_to_s3()
    maintenance_down()
    
def maintenance_up():
    """
    Install the Apache maintenance configuration.
    """
    sudo('cp -T %(repo_path)s/apache/%(settings)s/apache_maintenance %(apache_config_path)s' % env)
    reboot()

def gzip_assets():
    """
    GZips every file in the assets directory and places the new file
    in the gzip directory with the same filename.
    """
    run('cd %(repo_path)s; python gzip_assets.py' % env)

def reboot(): 
    """
    Restart the Apache2 server.
    """
    sudo('/mnt/apps/bin/restart-all-apache.sh')
    
def maintenance_down():
    """
    Reinstall the normal site configuration.
    """
    install_apache_conf()
    reboot()
    
"""
Commands - rollback
"""
def rollback(commit_id):
    """
    Rolls back to specified git commit hash or tag.
    
    There is NO guarantee we have committed a valid dataset for an arbitrary
    commit hash.
    """
    _confirm_branch()
    
    require('settings', provided_by=[production, staging])
    require('branch', provided_by=[stable, master, branch])
    
    maintenance_up()
    checkout_latest()
    git_reset(commit_id)
    gzip_assets()
    deploy_to_s3()
    maintenance_down()
    
def git_reset(commit_id):
    """
    Reset the git repository to an arbitrary commit hash or tag.
    """
    env.commit_id = commit_id
    run("cd %(repo_path)s; git reset --hard %(commit_id)s" % env)

"""
Commands - data
"""
def load_new_data():
    """
    Erase the current database and load new data from the SQL dump file.
    """
    require('settings', provided_by=[production, staging])
    
    maintenance_up()
    load_data()
    maintenance_down()

"""
Commands - miscellaneous
"""
    
def clear_cache():
    """
    Restart memcache, wiping the current cache.
    
    TODO: only clear site cache
    """
    sudo('service varnish restart')
    
def echo_host():
    """
    Echo the current host to the command line.
    """
    run('echo %(settings)s; echo %(hosts)s' % env)

"""
Deaths, destroyers of worlds
"""
def shiva_the_destroyer():
    """
    Remove all directories, databases, etc. associated with the application.
    """
    with settings(warn_only=True):
        sudo('rm -Rf %(path)s' % env)
        sudo('rm -Rf %(log_path)s' % env)
        sudo('rm %(apache_config_path)s' % env)
        reboot()

def _confirm_branch():
    if (env.settings == 'production' and env.branch != 'stable'):
        answer = prompt("You are trying to deploy the '%(branch)s' branch to production.\nYou should really only deploy a stable branch.\nDo you know what you're doing?" % env, default="Not at all")
        if answer not in ('y','Y','yes','Yes','buzz off','screw you'):
            exit()
