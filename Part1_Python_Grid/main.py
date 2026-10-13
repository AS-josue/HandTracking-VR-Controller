import cv2
import mediapipe as mp
import numpy as np
import os
import socket
import struct
import uuid

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Chemin vers le modèle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "hand_landmarker.task")
OUTPUT_DIR = os.path.join(BASE_DIR, "Output_images")

# Automatically create the output folder if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize the webcam
# Tip: change 0 to 1 if your primary webcam doesn't open or if you are using an external camera)
cap = cv2.VideoCapture(0)

# Configuration for the detector (MediaPipe HandLandmarker)
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=2,                         # Maximum number of hands
    min_hand_detection_confidence=0.8,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)

# Create the detector
detector = vision.HandLandmarker.create_from_options(options)

# UDP configuration
UDP_IP = "127.0.0.1"   # localhost → Unity and Python on the same PC
UDP_PORT = 5065
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Initial cursor position on the 2D Grid (HUD) in the terminal
object_position_x = 17
object_position_y = 17

board = [[' ' for _ in range(36)] for _ in range(35)]
board[object_position_x][object_position_y] = '#'

def draw_grid_overlay(image, board):
    h, w, _ = image.shape
    
    font = cv2.FONT_HERSHEY_PLAIN
    # Scale is adjusted based on the screen width to maintain proper proportions
    font_scale = max(0.4, w / 1400)  
    thickness = 1
    
    # Sample of a full line (36 characters) to measure its actual width in pixels
    sample_row = "".join(board[0])
    (text_width, text_height), baseline = cv2.getTextSize(sample_row, font, font_scale, thickness)
    
    # Clean safety margin from the right edge of the video (e.g., 25 pixels)
    start_x = int(w - text_width - 25)
    start_y = 35
    line_height = int(text_height + 4) # Small dynamic vertical spacing between lines
    
    # Semi-transparent background perfectly fitted to the actual size of the grid
    overlay = image.copy()
    box_padding = 10
    
    # Explicitly force conversion to (int, int) for both points
    pt1 = (int(start_x - box_padding), int(start_y - text_height - box_padding))
    pt2 = (int(start_x + text_width + box_padding), int(start_y + (len(board) * line_height) + box_padding))
    cv2.rectangle(overlay, pt1, pt2, (0, 0, 0), -1)

    alpha = 0.5  # Background transparency
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Draw each grid line on the image
    for i, row in enumerate(board):
        row_str = "".join(row)
        y_pos = int(start_y + (i * line_height))
        if y_pos < h - 10: # Safety check to prevent overflowing at the bottom
            # (start_x, y_pos) are now guaranteed to be integers
            cv2.putText(image, row_str, (start_x, y_pos), font, font_scale, (0, 255, 255), thickness, cv2.LINE_AA)

# Function to get the label (Left/Right)
def get_label(index, results):
    if results.handedness and len(results.handedness) > index:
        category = results.handedness[index][0]
        
        # Invert Left and Right to match the mirrored reality of the webcam
        original_label = category.category_name
        label = "Right" if original_label == "Left" else "Left"
        
        return label, round(category.score, 2)
    return "Unknown", 0.0

joint_list = [[8, 6, 5]]

alternate = 1 # Means "false"
captures_num = 0 # Means "none" (change this value to automatically capture images (e.g., 5))

# Function combining angle calculation and cursor movement within the grid
def process_hand_interactions(image, hand_landmarks, width, height):
    global object_position_x, object_position_y

    # 1. Proper gesture condition (3D Euclidean distance between Thumb / Middle finger)
    thumb_tip = np.array([hand_landmarks[4].x, hand_landmarks[4].y, hand_landmarks[4].z])
    middle_tip = np.array([hand_landmarks[12].x, hand_landmarks[12].y, hand_landmarks[12].z])
    is_pinched = np.linalg.norm(thumb_tip - middle_tip) < 0.06

    # 2. Display angles and cursor movements in the terminal grid if the gesture is validated
    if is_pinched:
        # Angle calculations
        # Iterate through the joint triplet(s) in the joints_list
        for joint in joint_list:
            a = np.array([hand_landmarks[joint[0]].x, hand_landmarks[joint[0]].y])
            b = np.array([hand_landmarks[joint[1]].x, hand_landmarks[joint[1]].y])
            c = np.array([hand_landmarks[joint[2]].x, hand_landmarks[joint[2]].y])
    
            radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
            angle = np.abs(radians * 180 / np.pi)
            
            if angle > 180:
                angle = 360 - angle

            # Extract X and Y coordinates by forcing standard int format
            text_x = int(b[0] * width)
            text_y = int(b[1] * height)

            cv2.putText(image, str(round(angle, 2)), (text_x, text_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                
        board[object_position_x][object_position_y] = ' ' 
        
        if (hand_landmarks[8].x > hand_landmarks[5].x and hand_landmarks[8].x > hand_landmarks[7].x) and object_position_y != 35:
            object_position_y += 1
        elif (hand_landmarks[8].x < hand_landmarks[5].x and hand_landmarks[8].x < hand_landmarks[7].x) and object_position_y != 0:
            object_position_y -= 1
        
        if (hand_landmarks[8].y < hand_landmarks[5].y and hand_landmarks[8].y < hand_landmarks[9].y and hand_landmarks[8].y < hand_landmarks[7].y) and object_position_x != 0:
            object_position_x -= 1
        elif (hand_landmarks[8].y > hand_landmarks[5].y and hand_landmarks[8].y > hand_landmarks[9].y or hand_landmarks[8].y > hand_landmarks[7].y) and object_position_x != 34:
            object_position_x += 1
        
        board[object_position_x][object_position_y] = '#' 
    
    return image

# Main loop
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Mirroring and converting from BGR to RGB
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Get image dimensions in pixels
    h, w, _ = frame.shape

    # Encapsulate for MediaPipe Tasks
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Landmark detection
    results = detector.detect(mp_image)

    # Check detections
    # print(results) 

    # If landmarks are detected, render the results
    if results.hand_landmarks:
        # Iterate through each detected hand
        for num, hand_landmarks in enumerate(results.hand_landmarks):
            # Create a flat array to send via UDP: x1,y1,z1,... x21,y21,z21
            data = []
            
            # Iterate through the 21 hand landmarks
            for lm in hand_landmarks:
                data.extend([lm.x, lm.y, lm.z])  # Normalized coordinates 0→1

                # Convert normalized coordinates (0 to 1) to pixels
                cx, cy = int(lm.x * w), int(lm.y * h)

                # Draw a point on the detected joint
                cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

            # Convert the array to bytes (float32) - UDP transmission
            sock.sendto(struct.pack(f'{len(data)}f', *data), (UDP_IP, UDP_PORT))

            # Draw lines to connect the joints (hand skeleton)
            # List of connections between hand landmarks
            HAND_CONNECTIONS = [
                (0,1),(1,2),(2,3),(3,4),      # Thumb
                (0,5),(5,6),(6,7),(7,8),      # Index
                (0,9),(9,10),(10,11),(11,12), # Middle
                (0,13),(13,14),(14,15),(15,16), # Ring
                (0,17),(17,18),(18,19),(19,20)  # Pinky
            ] # Point 0 is the wrist.

            for connection in HAND_CONNECTIONS:
                start_idx, end_idx = connection
                start_lm = hand_landmarks[start_idx]
                end_lm = hand_landmarks[end_idx]
                
                x1, y1 = int(start_lm.x * w), int(start_lm.y * h)
                x2, y2 = int(end_lm.x * w), int(end_lm.y * h)
                
                cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)  # White, thickness 2

            # Display the label (Left / Right)
            label, score = get_label(num, results)
            wrist = hand_landmarks[0]
            cv2.putText(frame, f"{label} {score}", (int(wrist.x * w), int(wrist.y * h)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)

            # Finger counting (raised fingers)
            fingers_number = 0
            tipId = [8, 12, 16, 20]
            for i in range(0, 4):
                if hand_landmarks[tipId[i]].y <= hand_landmarks[tipId[i] - 2].y:
                    fingers_number += 1
            
            if hand_landmarks[4].x < hand_landmarks[3].x and hand_landmarks[4].x < hand_landmarks[17].x:
                fingers_number += 1
            elif hand_landmarks[4].x > hand_landmarks[3].x and hand_landmarks[4].x > hand_landmarks[17].x:
                fingers_number += 1
            
            # Alternating display of the finger count
            if alternate == 1:
                cv2.putText(frame, str(fingers_number), (100, 75), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                alternate = 0
            else:
                cv2.putText(frame, str(fingers_number), (100, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                alternate = 1

            # Call custom logic (angles + terminal grid movement)
            process_hand_interactions(frame, hand_landmarks, w, h)
            
        # Display the grid overlay in the corner of the image
        draw_grid_overlay(frame, board)

    # Save images if requested
    if captures_num > 0 and results.hand_landmarks:
        cv2.imwrite(os.path.join(OUTPUT_DIR, '{}.jpg'.format(uuid.uuid1())), frame)
        captures_num -= 1

    cv2.imshow("Hand Tracking (HUD Grid)", frame)
    if cv2.waitKey(10) & 0xFF == 27:  # Press ESC to exit
        break

cap.release()
cv2.destroyAllWindows()