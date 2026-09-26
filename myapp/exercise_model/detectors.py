import os
import cv2
import numpy as np
from django.conf import settings
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class BaseExerciseDetector:
    def __init__(self):
        model_path = os.path.join(settings.BASE_DIR, 'myapp', 'pose_landmarker_lite.task')
        
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            min_pose_detection_confidence=0.7,
            min_pose_presence_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)

    @staticmethod
    def calculate_angle(a, b, c):
        a, b, c = np.array(a), np.array(b), np.array(c)
        radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
        angle = np.abs(radians * 180.0 / np.pi)
        return 360.0 - angle if angle > 180.0 else angle

    @staticmethod
    def calculate_vertical_deviation(p1, p2):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return np.degrees(np.arctan2(np.abs(dx), np.abs(dy)))
    def _draw_counter_box(self,img,counter,accuracy,calories_burned,w,h):
        box_w, box_h = 200, 110
        x1, y1 = w - box_w, h - box_h
        cv2.rectangle(img, (x1, y1), (w, h), (0, 0, 220), -1)
        cv2.putText(img, str(counter), (x1 + 20, y1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3)
        cv2.putText(img, f"Accuracy: {accuracy}%", (x1 + 10, y1 + 75), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(img, f"Calories: {calories_burned} kcal", (x1 + 10, y1 + 95), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

class PushupDetector(BaseExerciseDetector):
     def process_frame(self, img, session_data):
            h, w, _ = img.shape
            image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            detection_result = self.detector.detect(mp_image)
    
            counter = session_data['counter']
            total_attempts = session_data['total_attempts']
            accuracy = 100.0 if total_attempts == 0 else round((counter / total_attempts) * 100, 1)
            calories_burned = round(counter * 0.45, 2)
    
            if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                lm = detection_result.pose_landmarks[0]
                required_indices = [11, 13, 15, 23, 27]
    
                if not all(lm[idx].visibility >= 0.6 for idx in required_indices):
                    cv2.rectangle(img, (10, 10), (w - 10, 60), (0, 0, 255), -1)
                    cv2.putText(img, "Place camera at LEFT side & show FULL body", 
                                (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                else:
                    shoulder = [lm[11].x * w, lm[11].y * h]
                    elbow    = [lm[13].x * w, lm[13].y * h]
                    wrist    = [lm[15].x * w, lm[15].y * h]
                    hip      = [lm[23].x * w, lm[23].y * h]
                    ankle    = [lm[27].x * w, lm[27].y * h]
    
                    elbow_angle = self.calculate_angle(shoulder, elbow, wrist)
                    body_angle  = self.calculate_angle(shoulder, hip, ankle)
                    forearm_deviation = self.calculate_vertical_deviation(elbow, wrist)
    
                    is_body_straight = 160 <= body_angle <= 195
                    is_hand_pointing_down = forearm_deviation <= 30.0
                    is_form_valid = is_body_straight and is_hand_pointing_down
    
                    if elbow_angle >= 155 and session_data['stage'] != "down":
                        session_data['top_shoulder_y'] = shoulder[1]
    
                    top_y = session_data['top_shoulder_y']
                    shoulder_drop = (shoulder[1] - top_y) if top_y is not None else 0
                    has_actual_body_movement = shoulder_drop >= (h * 0.08)
    
                    if not is_form_valid:
                        session_data['bad_form_flag'] = True
    
                    if elbow_angle <= 95 and is_form_valid and has_actual_body_movement:
                        if session_data['stage'] != "down":
                            session_data['stage'] = "down"
    
                    if elbow_angle >= 155 and session_data['stage'] == "down":
                        session_data['total_attempts'] += 1
                        if not session_data['bad_form_flag']:
                            session_data['counter'] += 1
                        session_data['stage'] = "up"
                        session_data['bad_form_flag'] = False
    
                    counter = session_data['counter']
                    total_attempts = session_data['total_attempts']
                    accuracy = round((counter / total_attempts) * 100, 1) if total_attempts > 0 else 100.0
                    calories_burned = round(counter * 0.45, 2)
    
                    per = np.interp(elbow_angle, (90, 160), (100, 0))
                    bar = np.interp(elbow_angle, (90, 160), (100, 400))
    
                    if is_form_valid and (has_actual_body_movement or session_data['stage'] == "up"):
                        status_msg, banner_color = "Perfect Form!", (0, 200, 0)
                    elif not has_actual_body_movement and elbow_angle < 130:
                        status_msg, banner_color = "Fake Movement! Lower Body", (0, 0, 255)
                    elif not is_body_straight:
                        status_msg, banner_color = "Keep Body Straight!", (0, 0, 255)
                    else:
                        status_msg, banner_color = "Bad Form: Check Forearms!", (0, 0, 255)
    
                    # Draw Visual Feedback
                    cv2.rectangle(img, (150, 20), (640, 60), banner_color, -1)
                    cv2.putText(img, status_msg, (160, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    cv2.line(img, tuple(np.int32(shoulder)), tuple(np.int32(elbow)), (255, 255, 255), 2)
                    cv2.line(img, tuple(np.int32(hip)), tuple(np.int32(shoulder)), (255, 255, 255), 2)
                    cv2.line(img, tuple(np.int32(hip)), tuple(np.int32(ankle)), (255, 255, 255), 2)
    
                    forearm_color = (0, 255, 0) if is_hand_pointing_down else (0, 0, 255)
                    cv2.line(img, tuple(np.int32(elbow)), tuple(np.int32(wrist)), forearm_color, 4)
    
                    for pt in [shoulder, elbow, wrist, hip, ankle]:
                        cv2.circle(img, tuple(np.int32(pt)), 6, (255, 0, 255), -1)
    
                    cv2.rectangle(img, (w - 50, 100), (w - 20, 400), (50, 50, 50), 2)
                    cv2.rectangle(img, (w - 50, int(bar)), (w - 20, 400), banner_color, -1)
                    cv2.putText(img, f"{int(per)}%", (w - 65, 435), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
            # Draw Bottom-Right Counter Box with Calories
            self._draw_counter_box(img, counter, accuracy, calories_burned, w, h)
            return img, counter, accuracy, calories_burned

class SitupDetector(BaseExerciseDetector):
    def process_frame(self, img, session_data):
        h, w, _ = img.shape
        image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = self.detector.detect(mp_image)

        counter = session_data['counter']
        total_attempts = session_data['total_attempts']
        accuracy = 100.0 if total_attempts == 0 else round((counter / total_attempts) * 100, 1)
        calories_burned = round(counter * 0.50, 2)  # ~0.50 kcal per sit-up

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            lm = detection_result.pose_landmarks[0]
            # Shoulder, Hip, Knee, Ankle
            required_indices = [11, 23, 25, 27]

            if not all(lm[idx].visibility >= 0.6 for idx in required_indices):
                cv2.rectangle(img, (10, 10), (w - 10, 60), (0, 0, 255), -1)
                cv2.putText(img, "Place camera at SIDE view & show FULL body", 
                            (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            else:
                shoulder = [lm[11].x * w, lm[11].y * h]
                hip      = [lm[23].x * w, lm[23].y * h]
                knee     = [lm[25].x * w, lm[25].y * h]
                ankle    = [lm[27].x * w, lm[27].y * h]

                # Main sit-up flexion angle (Shoulder - Hip - Knee)
                hip_angle = self.calculate_angle(shoulder, hip, knee)
                # Ensure knees stay bent (Hip - Knee - Ankle)
                knee_angle = self.calculate_angle(hip, knee, ankle)

                is_knees_bent = 40 <= knee_angle <= 130
                is_form_valid = is_knees_bent

                if not is_form_valid:
                    session_data['bad_form_flag'] = True

                # Down position: Lying down flat (hip angle open, ~130-180 deg)
                if hip_angle >= 130 and session_data['stage'] != "down":
                    session_data['stage'] = "down"

                # Up position: Sitting up fully (hip angle closed, <= 60 deg)
                if hip_angle <= 60 and session_data['stage'] == "down":
                    session_data['total_attempts'] += 1
                    if not session_data['bad_form_flag']:
                        session_data['counter'] += 1
                    session_data['stage'] = "up"
                    session_data['bad_form_flag'] = False

                counter = session_data['counter']
                total_attempts = session_data['total_attempts']
                accuracy = round((counter / total_attempts) * 100, 1) if total_attempts > 0 else 100.0
                calories_burned = round(counter * 0.50, 2)

                per = np.interp(hip_angle, (50, 140), (100, 0))
                bar = np.interp(hip_angle, (50, 140), (100, 400))

                if is_form_valid:
                    status_msg, banner_color = "Good Form!", (0, 200, 0)
                else:
                    status_msg, banner_color = "Keep Knees Bent!", (0, 0, 255)

                # Draw skeleton lines
                cv2.rectangle(img, (150, 20), (640, 60), banner_color, -1)
                cv2.putText(img, status_msg, (160, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

                cv2.line(img, tuple(np.int32(shoulder)), tuple(np.int32(hip)), (255, 255, 255), 3)
                cv2.line(img, tuple(np.int32(hip)), tuple(np.int32(knee)), (255, 255, 255), 3)

                knee_color = (0, 255, 0) if is_knees_bent else (0, 0, 255)
                cv2.line(img, tuple(np.int32(knee)), tuple(np.int32(ankle)), knee_color, 4)

                for pt in [shoulder, hip, knee, ankle]:
                    cv2.circle(img, tuple(np.int32(pt)), 6, (255, 0, 255), -1)

                cv2.rectangle(img, (w - 50, 100), (w - 20, 400), (50, 50, 50), 2)
                cv2.rectangle(img, (w - 50, int(bar)), (w - 20, 400), banner_color, -1)
                cv2.putText(img, f"{int(per)}%", (w - 65, 435), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        self._draw_counter_box(img, counter, accuracy, calories_burned, w, h)
        return img, counter, accuracy, calories_burned


class SquatDetector(BaseExerciseDetector):
    def process_frame(self, img, session_data):
        h, w, _ = img.shape
        image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = self.detector.detect(mp_image)

        counter = session_data['counter']
        total_attempts = session_data['total_attempts']
        accuracy = 100.0 if total_attempts == 0 else round((counter / total_attempts) * 100, 1)
        calories_burned = round(counter * 0.32, 2)  # ~0.32 kcal per squat

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            lm = detection_result.pose_landmarks[0]
            # Shoulder, Hip, Knee, Ankle
            required_indices = [11, 23, 25, 27]

            if not all(lm[idx].visibility >= 0.6 for idx in required_indices):
                cv2.rectangle(img, (10, 10), (w - 10, 60), (0, 0, 255), -1)
                cv2.putText(img, "Place camera at SIDE view & show FULL body", 
                            (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            else:
                shoulder = [lm[11].x * w, lm[11].y * h]
                hip      = [lm[23].x * w, lm[23].y * h]
                knee     = [lm[25].x * w, lm[25].y * h]
                ankle    = [lm[27].x * w, lm[27].y * h]

                # Knee flexion angle (Hip - Knee - Ankle)
                knee_angle = self.calculate_angle(hip, knee, ankle)
                # Back alignment check (Shoulder - Hip - Knee)
                back_angle = self.calculate_angle(shoulder, hip, knee)

                is_back_upright = back_angle >= 70.0
                is_form_valid = is_back_upright

                if not is_form_valid:
                    session_data['bad_form_flag'] = True

                # Standing position: Leg extended (Knee angle >= 160 deg)
                if knee_angle >= 160 and session_data['stage'] != "up":
                    session_data['stage'] = "up"

                # Deep squat position: Knee angle <= 95 deg
                if knee_angle <= 95 and is_form_valid and session_data['stage'] == "up":
                    if session_data['stage'] != "down":
                        session_data['stage'] = "down"

                # Return to standing position completes the rep
                if knee_angle >= 160 and session_data['stage'] == "down":
                    session_data['total_attempts'] += 1
                    if not session_data['bad_form_flag']:
                        session_data['counter'] += 1
                    session_data['stage'] = "up"
                    session_data['bad_form_flag'] = False

                counter = session_data['counter']
                total_attempts = session_data['total_attempts']
                accuracy = round((counter / total_attempts) * 100, 1) if total_attempts > 0 else 100.0
                calories_burned = round(counter * 0.32, 2)

                per = np.interp(knee_angle, (90, 160), (100, 0))
                bar = np.interp(knee_angle, (90, 160), (100, 400))

                if is_form_valid:
                    status_msg, banner_color = "Good Form!", (0, 200, 0)
                else:
                    status_msg, banner_color = "Keep Chest Up!", (0, 0, 255)

                # Draw skeleton lines
                cv2.rectangle(img, (150, 20), (640, 60), banner_color, -1)
                cv2.putText(img, status_msg, (160, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

                back_color = (0, 255, 0) if is_back_upright else (0, 0, 255)
                cv2.line(img, tuple(np.int32(shoulder)), tuple(np.int32(hip)), back_color, 4)
                cv2.line(img, tuple(np.int32(hip)), tuple(np.int32(knee)), (255, 255, 255), 3)
                cv2.line(img, tuple(np.int32(knee)), tuple(np.int32(ankle)), (255, 255, 255), 3)

                for pt in [shoulder, hip, knee, ankle]:
                    cv2.circle(img, tuple(np.int32(pt)), 6, (255, 0, 255), -1)

                cv2.rectangle(img, (w - 50, 100), (w - 20, 400), (50, 50, 50), 2)
                cv2.rectangle(img, (w - 50, int(bar)), (w - 20, 400), banner_color, -1)
                cv2.putText(img, f"{int(per)}%", (w - 65, 435), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        self._draw_counter_box(img, counter, accuracy, calories_burned, w, h)
        return img, counter, accuracy, calories_burned

    
def get_exercise_detector(exercise_type):
    detectors = {
        'pushup': PushupDetector,
        'situp': SitupDetector,
        'squat': SquatDetector,
    }
    detector_cls = detectors.get(exercise_type.lower(), PushupDetector)
    return detector_cls()
