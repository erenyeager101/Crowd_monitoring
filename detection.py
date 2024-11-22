import cv2
import os
import datetime
import imutils
import numpy as np
import requests
import threading
from pymongo import MongoClient
import json
from bson import ObjectId

protopath = "MobileNetSSD_deploy.prototxt"
modelpath = "MobileNetSSD_deploy.caffemodel"

CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

SERVER_URL = 'http://localhost:3000/update_data'

CAMERAS = [
    {"source": "https://drive.google.com/uc?export=download&id=1i7wbKo3u7H1nW92BO_kMUHcOI2qgIDvY" , "coordinates": {"latitude": 18.5204, "longitude": 73.8567}},
    {"source": "https://drive.google.com/uc?export=download&id=14gTAyQm1cvn3bF7eETKLof6PZ3c55hYU" , "coordinates":{"latitude": 18.5369, "longitude": 73.8567}},
    {"source": 0 , "coordinates": {"latitude": 18.5850, "longitude": 73.8567}}
]

client = MongoClient("mongodb+srv://kunalsonne:kunalsonne1847724@cluster0.95mdg.mongodb.net/?retryWrites=true&w=majority")
db = client['home']
collection = db['blogs']

frame_skip = 11  


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

def send_data(count, coordinates):
    data = {
        'count': count,
        'coordinates': coordinates,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        result = collection.insert_one(data)
        data['_id'] = result.inserted_id  
        print(f"Data inserted into MongoDB: {data}")
    except Exception as e:
        print(f"Error inserting into MongoDB: {e}")

    try:
        json_data = json.dumps(data, cls=JSONEncoder) 
        response = requests.post(SERVER_URL, data=json_data, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print("Data sent successfully")
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to server: {e}")

def process_camera(cam_source, coordinates, window_name):
    print(f"Starting camera {window_name} with source: {cam_source}")
    cap = cv2.VideoCapture(cam_source)
    if not cap.isOpened():
        print(f"Failed to open camera source: {cam_source}")
        return

    detector = cv2.dnn.readNetFromCaffe(prototxt=protopath, caffeModel=modelpath)
    total_frames = 0
    count = 0
    start_time = datetime.datetime.now()
    frame_skip = 5 

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"Failed to grab frame from source {cam_source}. Exiting...")
            break

        total_frames += 1
        if total_frames % frame_skip != 0: 
            continue

        frame = imutils.resize(frame, width=400)  
        (H, W) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
        detector.setInput(blob)
        person_detections = detector.forward()

        count = 0
        for i in np.arange(0, person_detections.shape[2]):
            confidence = person_detections[0, 0, i, 2]
            if confidence > 0.4:
                idx = int(person_detections[0, 0, i, 1])
                if CLASSES[idx] != "person":
                    continue

                person_box = person_detections[0, 0, i, 3:7] * np.array([W, H, W, H])
                (startX, startY, endX, endY) = person_box.astype("int")
                cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 0, 255), 2)
                count += 1

        print(f"{window_name} - Count: {count}")
        send_data(count, coordinates)  

        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        if elapsed_time > 0:  
            fps = total_frames / elapsed_time
        else:
            fps = 0 

        fps_text = f"FPS: {fps:.2f}"
        count_text = f"Count: {count}"
        cv2.putText(frame, fps_text, (5, 30), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 1)
        cv2.putText(frame, count_text, (5, 60), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 1)

        if "DISPLAY" in os.environ or os.name == 'nt':  
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()


def main():
    threads = []
    for idx, cam in enumerate(CAMERAS):
        window_name = f"Camera {idx + 1}"
        thread = threading.Thread(target=process_camera, args=(cam["source"], cam["coordinates"], window_name))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
