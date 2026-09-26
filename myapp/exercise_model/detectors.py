import os
import cv2
import numpy as np
from django.conf import settings
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class BaseExerciseDetector:
    def __init__(self):
        # Point to task file located inside exercise_model directory
        model_path = os.path.join(settings.BASE_DIR, 'myapp', 'pose_landmarker_lite.task')
        if not os.path.exists(model_path):
            # Fallback path if task file is directly inside myapp
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

    def _draw_counter_box(self, img, counter, accuracy, calories_burned, w, h):
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

        counter = session_data.get('counter', 0)
        total_attempts = session_data.get('total_attempts', 0)
        accuracy = 100.0 if total_attempts == 0 else round((counter / total_attempts) * 100, 1)
        calories_burned = round(counter * 0.45, 2)

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            lm = detection_result.pose_landmarks[0]
            required_indices = [11, 13, 15, 23, 27]
            if not all(lm[idx].visibility >= 0.6 for idx in required_indices):
                cv2.rectangle(img, (10, 10), (w - 10, 60), (0, 0, 255), -1)
                cv2.putText(img, "Show FULL body (Left side view)", (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            else:
                shoulder = [lm[11].x * w, lm[11].y * h]
                elbow    = [lm[13].x * w, lm[13].y * h]
                wrist    = [lm[15].x * w, lm[15].y * h]
                hip      = [lm[23].x * w, lm[23].y * h]
                ankle    = [lm[27].x * w, lm[27].y * h]

                elbow_angle = self.calculate_angle(shoulder, elbow, wrist)
                body_angle  = self.calculate_angle(shoulder, hip, ankle)
                forearm_dev = self.calculate_vertical_deviation(elbow, wrist)

                is_body_straight = 160 <= body_angle <= 195
                is_hand_down = forearm_dev <= 30.0
                is_form_valid = is_body_straight and is_hand_down

                if elbow_angle >= 155 and session_data.get('stage') != "down":
                    session_data['top_shoulder_y'] = shoulder[1]

                top_y = session_data.get('top_shoulder_y')
                shoulder_drop = (shoulder[1] - top_y) if top_y is not None else 0
                has_actual_movement = shoulder_drop >= (h * 0.08)

                if not is_form_valid:
                    session_data['bad_form_flag'] = True

                if elbow_angle <= 95 and is_form_valid and has_actual_movement:
                    if session_data.get('stage') != "down":
                        session_data['stage'] = "down"

                if elbow_angle >= 155 and session_data.get('stage') == "down":
                    session_data['total_attempts'] += 1
                    if not session_data.get('bad_form_flag', False):
                        session_data['counter'] += 1
                    session_data['stage'] = "up"
                    session_data['bad_form_flag'] = False

                counter = session_data['counter']
                total_attempts = session_data['total_attempts']
                accuracy = round((counter / total_attempts) * 100, 1) if total_attempts > 0 else 100.0
                calories_burned = round(counter * 0.45, 2)

                per = np.interp(elbow_angle, (90, 160), (100, 0))
                bar = np.interp(elbow_angle, (90, 160), (100, 400))
                status_msg, banner_color = ("Perfect Form!", (0, 200, 0)) if is_form_valid else ("Check Form!", (0, 0, 255))

                cv2.rectangle(img, (150, 20), (640, 60), banner_color, -1)
                cv2.putText(img, status_msg, (160, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                for line in [(shoulder, elbow), (elbow, wrist), (shoulder, hip), (hip, ankle)]:
                    cv2.line(img, tuple(np.int32(line[0])), tuple(np.int32(line[1])), (255, 255, 255), 2)

                cv2.rectangle(img, (w - 50, 100), (w - 20, 400), (50, 50, 50), 2)
                cv2.rectangle(img, (w - 50, int(bar)), (w - 20, 400), banner_color, -1)

        self._draw_counter_box(img, counter, accuracy, calories_burned, w, h)
        return img, counter, accuracy, calories_burned


class SquatDetector(BaseExerciseDetector):
    def process_frame(self, img, session_data):
        h, w, _ = img.shape
        image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = self.detector.detect(mp_image)

        counter = session_data.get('counter', 0)
        total_attempts = session_data.get('total_attempts', 0)
        accuracy = 100.0 if total_attempts == 0 else round((counter / total_attempts) * 100, 1)
        calories_burned = round(counter * 0.32, 2)

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            lm = detection_result.pose_landmarks[0]
            required_indices = [23, 25, 27]
            if all(lm[idx].visibility >= 0.6 for idx in required_indices):
                hip   = [lm[23].x * w, lm[23].y * h]
                knee  = [lm[25].x * w, lm[25].y * h]
                ankle = [lm[27].x * w, lm[27].y * h]

                knee_angle = self.calculate_angle(hip, knee, ankle)

                if knee_angle <= 90:
                    if session_data.get('stage') != "down":
                        session_data['stage'] = "down"

                if knee_angle >= 160 and session_data.get('stage') == "down":
                    session_data['total_attempts'] += 1
                    session_data['counter'] += 1
                    session_data['stage'] = "up"

                counter = session_data['counter']
                total_attempts = session_data['total_attempts']
                accuracy = round((counter / total_attempts) * 100, 1) if total_attempts > 0 else 100.0
                calories_burned = round(counter * 0.32, 2)

                cv2.line(img, tuple(np.int32(hip)), tuple(np.int32(knee)), (255, 255, 255), 3)
                cv2.line(img, tuple(np.int32(knee)), tuple(np.int32(ankle)), (255, 255, 255), 3)

        self._draw_counter_box(img, counter, accuracy, calories_burned, w, h)
        return img, counter, accuracy, calories_burned


class SitupDetector(BaseExerciseDetector):
    def process_frame(self, img, session_data):
        h, w, _ = img.shape
        image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = self.detector.detect(mp_image)

        counter = session_data.get('counter', 0)
        total_attempts = session_data.get('total_attempts', 0)
        accuracy = 100.0 if total_attempts == 0 else round((counter / total_attempts) * 100, 1)
        calories_burned = round(counter * 0.25, 2)

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            lm = detection_result.pose_landmarks[0]
            required_indices = [11, 23, 25]
            if all(lm[idx].visibility >= 0.6 for idx in required_indices):
                shoulder = [lm[11].x * w, lm[11].y * h]
                hip      = [lm[23].x * w, lm[23].y * h]
                knee     = [lm[25].x * w, lm[25].y * h]

                torso_angle = self.calculate_angle(shoulder, hip, knee)

                if torso_angle <= 55:
                    if session_data.get('stage') != "up":
                        session_data['stage'] = "up"

                if torso_angle >= 105 and session_data.get('stage') == "up":
                    session_data['total_attempts'] += 1
                    session_data['counter'] += 1
                    session_data['stage'] = "down"

                counter = session_data['counter']
                total_attempts = session_data['total_attempts']
                accuracy = round((counter / total_attempts) * 100, 1) if total_attempts > 0 else 100.0
                calories_burned = round(counter * 0.25, 2)

                cv2.line(img, tuple(np.int32(shoulder)), tuple(np.int32(hip)), (255, 255, 255), 3)
                cv2.line(img, tuple(np.int32(hip)), tuple(np.int32(knee)), (255, 255, 255), 3)

        self._draw_counter_box(img, counter, accuracy, calories_burned, w, h)
        return img, counter, accuracy, calories_burned


def get_detector(exercise_type):
    """Factory function to route exercise type to detector class."""
    exercise_type = str(exercise_type).lower()
    if 'squat' in exercise_type:
        return SquatDetector()
    elif 'situp' in exercise_type or 'sit-up' in exercise_type or 'crunch' in exercise_type:
        return SitupDetector()
    else:
        return PushupDetector()