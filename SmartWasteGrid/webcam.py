import cv2
from ultralytics import YOLO

model = YOLO("model/best.pt")

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open webcam")
    exit()

print("Webcam started. Press Q to quit.")

while True:
    ret, frame = cap.read()

    if not ret:
        print("ERROR: Could not read webcam")
        break

    results = model(frame, conf=0.25, verbose=False)

    annotated_frame = results[0].plot()

    cv2.imshow("SmartWasteGrid - Live Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()