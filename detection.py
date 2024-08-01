import cv2
import os
import datetime
import imutils
import numpy as np
import requests
import threading

protopath = "MobileNetSSD_deploy.prototxt"
modelpath = "MobileNetSSD_deploy.caffemodel"

CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

SERVER_URL = 'http://localhost:3000/update_data'

CAMERAS = [
    {"source": 0, "coordinates": {"latitude": 18.5204, "longitude": 73.8567}},
    {"source": "http://192.168.1.2:8080/video", "coordinates": {"latitude": 18.5304, "longitude": 73.8567}}
]

def send_data(count, coordinates):
    data = {
        'count': count,
        'coordinates': coordinates
    }
    try:
        response = requests.post(SERVER_URL, json=data)
        if response.status_code == 200:
            print("Data sent successfully")
        else:
            print("Failed to send data")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data: {e}")

def process_camera(cam_source, coordinates, window_name):
    print(f"Starting camera {window_name} with source: {cam_source}")
    cap = cv2.VideoCapture(cam_source)
    if not cap.isOpened():
        print(f"Failed to open camera source: {cam_source}")
        return

    detector = cv2.dnn.readNetFromCaffe(prototxt=protopath, caffeModel=modelpath)
    fps_start_time = datetime.datetime.now()
    total_frames = 0
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"Failed to grab frame from source {cam_source}. Exiting...")
            break

        frame = imutils.resize(frame, width=600)
        total_frames += 1

        (H, W) = frame.shape[:2]

        blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
        detector.setInput(blob)
        person_detections = detector.forward()

        count = 0
        for i in np.arange(0, person_detections.shape[2]):
            confidence = person_detections[0, 0, i, 2]
            if confidence > 0.5:
                idx = int(person_detections[0, 0, i, 1])
                if CLASSES[idx] != "person":
                    continue

                person_box = person_detections[0, 0, i, 3:7] * np.array([W, H, W, H])
                (startX, startY, endX, endY) = person_box.astype("int")
                cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 0, 255), 2)
                count += 1

        print(f"{window_name} - Count: {count}")
        send_data(count, coordinates)

        fps_end_time = datetime.datetime.now()
        time_diff = fps_end_time - fps_start_time
        if time_diff.seconds == 0:
            fps = 0.0
        else:
            fps = (total_frames / time_diff.seconds)

        fps_text = "FPS: {:.2f}".format(fps)
        count_text = "Count: {}".format(count)

        cv2.putText(frame, fps_text, (5, 30), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 1)
        cv2.putText(frame, count_text, (5, 60), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 1)

        if "DISPLAY" in os.environ or os.name == 'nt':  # Checks if a display is available
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

def main():
    threads = []
    for idx, cam in enumerate(CAMERAS):
        window_name = f"Camera {idx+1}"
        thread = threading.Thread(target=process_camera, args=(cam["source"], cam["coordinates"], window_name))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()



