import sys, os.path
import eventlet
from config import get_settings
from boto.s3.connection import S3Connection
#s3conn = eventlet.import_patched("boto.s3.connection")
#S3Connection = s3conn.S3Connection
from boto.s3.key import Key
import os
import mimetypes
import gzip
import tempfile
import logging
import shutil
eventlet.monkey_patch()

AWS_ACCESS_KEY_ID = "PUT_YOURS_HERE"
AWS_SECRET_ACCESS_KEY = "PUT_YOURS_HERE"
CONCURRENCY = 32

def _s3conn(aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY):
    return S3Connection(aws_access_key_id, aws_secret_access_key)

def deploy_to_s3(directory, bucket):
    """
    Deploy a directory to an s3 bucket using parallel uploads.
    """
    directory = directory.rstrip('/')
    slug = directory.split('/')[-1]

    tempdir = tempfile.mkdtemp('gallery')
    pool = eventlet.GreenPool(CONCURRENCY)
    for keyname, absolute_path in find_file_paths(directory):
        pool.spawn(s3_upload, slug, keyname, absolute_path, bucket, tempdir)

    pool.waitall()
    shutil.rmtree(tempdir,True)
    return True

def s3_upload(slug, keyname, absolute_path, bucket, tempdir):
    """
    Upload a file to s3
    """
    conn = _s3conn()
    bucket = conn.get_bucket(bucket)

    mimetype = mimetypes.guess_type(absolute_path)
    options = { 'Content-Type' : mimetype[0] }

    # There's a possible race condition if files have the same name
    key_parts = keyname.split('/')
    filename = key_parts.pop()

    if mimetype[0] is not None and mimetype[0].startswith('text/') and not filename.startswith('og_'):
        upload = open(absolute_path);
        options['Content-Encoding'] = 'gzip'
        temp_path = os.path.join(tempdir, filename)
        gzfile = gzip.open(temp_path, 'wb')
        gzfile.write(upload.read())
        gzfile.close()
        absolute_path = temp_path

    k = Key(bucket)
    k.key = '%s/%s' % (slug, keyname)
    k.set_contents_from_filename(absolute_path, options, policy='public-read')

def find_file_paths(directory):
    """
    A generator function that recursively finds all files in the upload directory.
    """
    for root, dirs, files in os.walk(directory):
        rel_path = os.path.relpath(root, directory)

        for f in files:
            if rel_path == '.':
                yield (f, os.path.join(root, f))
            else:
                yield (os.path.join(rel_path, f), os.path.join(root, f))

if __name__ == '__main__':
    settings = get_settings()
    for arg in sys.argv[1:]:
        deploy_to_s3(arg,settings['S3_BUCKET_NAME'])

