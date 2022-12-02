import subprocess, aiofiles, re, os, os.path, ffmpeg, sys, base64
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from os import listdir
from os.path import join, isdir, isfile

parent_dir_path = os.path.dirname(os.path.realpath(__file__))

def execute(command):
    process = subprocess.Popen(command, shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = ''
    for line in iter(process.stdout.readline, ''):
        output += line
    process.wait()
    exit_code = process.returncode

    if exit_code == 0:
        return output
    else:
        raise Exception(command, exit_code, output)


def get_archive():
    """Ensure that the archive file exists and return its path.

    This is a function so the path can be made configurable in the future.

    Returns:
        :obj:`str`: The full local path to the archive file.
    """
    filename = '/config/archive.txt'
    archfile = Path(filename)
    if not archfile.exists():
        archfile.touch()
    return filename


templates = Jinja2Templates(directory='/app/webserver/templates')
webserver = FastAPI()

youtubedl_binary = 'yt-dlp'

@webserver.get('/')
async def dashboard(request: Request):
    return templates.TemplateResponse('dashboard.html', {'request': request })

@webserver.get('/archive')
async def archive(request: Request ):
    # Get a list of all available channels
    channels = list_folder_content()
    return templates.TemplateResponse('channel_archive.html', {'request': request, 'items': channels, 'type': 'archive'})

@webserver.get('/archive/{channel}')
async def channel(request: Request, channel):
    # Get all a list of all files
    files = list_folder_content(channel, False)
    items = get_video_data(files, channel)
    return templates.TemplateResponse('channel_archive.html', {'request': request, 'items': items, 'type': 'channel'})

# @webserver.get('/archive/{channel}/{video_id}')
# async def channel(request: Request, channel, video_id):
#     return templates.TemplateResponse('channel_video_detail.html', {'request': request, 'items': list_folder_content(channel, False), 'type': 'detail'})


def read_file(file_name):
    binary_fc = open(file_name, 'rb').read()
    base64_utf8_str = base64.b64encode(binary_fc).decode('utf-8')
    ext = file_name.split('.')[-1]
    return f'data:image/{ext};base64,{base64_utf8_str}'

def get_video_data(filenames, channel):
    output = list()
    for file in filenames:
        fullfilepath = "/downloads/" + channel + "/" + file
        outfilepath = "/downloads/" + channel + "/" + file + "_thumbnail.jpg"
        metadata = ffmpeg.probe(fullfilepath)
        filepath = metadata['format']['filename']
        video_name = filepath.split('/')[-1].split('.')[0]
        time = float(metadata['streams'][0]['duration']) // 2
        width = float(metadata['streams'][0]['width'])
        try:
            (
                ffmpeg
                .input(fullfilepath, ss=time)
                .filter('scale', width, -1)
                .output(outfilepath, vframes=1)
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            print(e.stderr.decode(), file=sys.stderr)
        
        output.append({
            'filepath': filepath,
            'thumbnail': outfilepath,
            'video_title': video_name,
            'video_url': fullfilepath
        })
    return output

def list_folder_content(path = "", onlyDir = True):
    if path == "":
        downloadPath = '/downloads'
        return [f for f in listdir(downloadPath) if (onlyDir and isdir(join(downloadPath, f))) or (not onlyDir and isfile(join(downloadPath, f)))]
    else:
        list = listdir('/downloads/' + path)
        return [ file for file in list if file.endswith('.mp4')]

@webserver.post('/download')
async def download_url(url: str = Form(...)):
    if url is not False:
        async with aiofiles.open('/config/args.conf') as f:
            if re.search(r'(--format |-f )', await f.read(), flags=re.I | re.MULTILINE) is not None:
                youtubedl_args_format = ''
            else:
                youtubedl_args_format = youtubedl_default_args_format
        execute(f'{youtubedl_binary} \'{url}\' --no-playlist-reverse --playlist-end \'-1\' --config-location \'/config/args.conf\' {youtubedl_args_format}')
    return RedirectResponse(url='/', status_code=303)


@webserver.get('/edit/args')
async def edit_args(request: Request):
    args = ''
    async with aiofiles.open('/config/args.conf') as f:
        async for line in f:
            args = args + line
    return templates.TemplateResponse('args.html', {'request': request, 'args': args})


@webserver.post('/edit/args/save')
async def save_args(args_new: list = Form(...)):
    async with aiofiles.open('/config/args.conf', mode='w') as f:
        for line in args_new:
            await f.write(line.replace('\r\n', '\n'))
    return RedirectResponse(url='/edit/args', status_code=303)


@webserver.get('/edit/channels')
async def edit_channels(request: Request):
    channels = ''
    async with aiofiles.open('/config/channels.txt') as f:
        async for line in f:
            channels = channels + line
    return templates.TemplateResponse('channels.html', {'request': request, 'channels': channels})


@webserver.post('/edit/channels/save')
async def save_channels(channels_new: list = Form(...)):
    async with aiofiles.open('/config/channels.txt', mode='w') as f:
        for line in channels_new:
            await f.write(line.replace('\r\n', '\n'))
    return RedirectResponse(url='/edit/channels', status_code=303)


@webserver.get('/edit/archive')
async def edit_archive(request: Request):
    archive = ''
    async with aiofiles.open(get_archive()) as f:
        async for line in f:
            archive = archive + line
    return templates.TemplateResponse('archive.html', {'request': request, 'archive': archive})


@webserver.post('/edit/archive/save')
async def save_archive(archive_new: list = Form(...)):
    async with aiofiles.open('/config/archive.txt', mode='w') as f:
        for line in archive_new:
            await f.write(line.replace('\r\n', '\n'))
    return RedirectResponse(url='/edit/archive', status_code=303)


@webserver.get('/favicon.ico')
async def favicon():
    return FileResponse('/app/webserver/static/favicon.png')

webserver.mount("/downloads", StaticFiles(directory="/downloads"), name="downloads")


with open('/config.default/format') as default_format:
    youtubedl_default_args_format = f'--format "{str(default_format.read()).strip()}"'
