
import validators
import time
import libs

import cv2

from flask import Flask, request
from threading import Thread

from multiprocessing import Lock

import traceback

# As per https://stackoverflow.com/questions/28423069/store-large-data-or-a-service-connection-per-flask-session
ih_connection = None
flask_app = Flask(__name__)
lock = Lock()

CAMERA_CAPTURE_SIZE = (640, 480)
FINAL_SIZE = (1280, 720)

# =======================
#  Temp stuff, this will be removed
# =======================

def tmp_get_random_bg() -> str:
    import os, sys, pathlib, random
    bg_path = os.path.join(pathlib.Path(sys.modules['__main__'].__file__).resolve().parent, 'backgrounds')
    file_list = [file for file in os.listdir(bg_path) if not file.endswith(".mp4")]
    return random.choice(file_list)

# =======================
#  Temp stuff end
# =======================


# Dont actually need to lock this...
def get_ih() -> libs.image_handler.Image_Handler:
    with lock:
        global ih_connection
        if not ih_connection:
            ih_connection = libs.image_handler.Image_Handler(
                background_filename=tmp_get_random_bg(),
                effect=libs.effects.available_effects.lipstick
            )
        return ih_connection

# =======================
#  Move flask stuff to another file
# =======================

# Perhaps we keep settings in a json file and trigger a reload here after modifying it?

@flask_app.route('/', methods=['POST'])
def change_on_request():
    ih = get_ih()
    try:
        req = request.get_json()
        download_status = True
        if 'url' in req and 'filename' in req:
            if validators.url(req['url']):
                download_status = ih.download_object(req['url'], req['filename'])
        if 'filename' in req and download_status:
            ih.change_background(req['filename'])
    except Exception as e:
        print(e)
        return "There was a fucky wucky\n"
    return f"Changed to {req['filename']}!\n"

def start_flask():
    # Init Flask
    kwargs = {'host': '127.0.0.1', 'port': 9987, 'threaded': True, 'use_reloader': False, 'debug': False}
    Thread(target=flask_app.run, daemon=True, kwargs=kwargs).start()

# =======================

def main():
    # This takes the longes to "warm up"
    bodypix = libs.bodypix.BodyPix()

    # We need to see what we're doing :)
    camera = libs.camera.Camera()
    
    # Set up the image handler
    ih = get_ih()
    ih.change_background(ih.background_filename)

    # Start flask after pre flight is done    
    start_flask()

    # Loops per second
    iter = 0

    start = time.time()

    # frames forever
    while True:
        iter += 1
        try:
            frame = camera.get_frame()
            frame = ih.apply_effect(frame)

            mask = bodypix.get_mask(capture=frame)
            mask = ih.refine_mask(mask)

            composited_frame = ih.composite_frames(capture=frame, mask=mask)

            final_frame = cv2.resize(composited_frame, FINAL_SIZE)

            camera.schedule_frame(final_frame)
        except libs.camera.CameraCaptureError as e:
            print("The camera failed to capture a frame.\n\tSleeping now for a few seconds.")
            time.sleep(3)
        except Exception as e:
            # The best way to handle exceptions is obviously to just catch them all :)
            time.sleep(1)
            print(e)
            print(traceback.format_exc())
            quit()

        if time.time() > start + 5:
            print(f"Loops in the last 5 seconds: {iter}\n\tAvg: {iter / 5}")
            start = time.time()
            iter = 0


if __name__ == "__main__":
    main()

