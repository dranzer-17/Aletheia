import numpy as np
import cv2
import face_recognition

def face_rec(frames, p=None, klass=None):
    temp_face = np.zeros((len(frames), 224, 224, 3), dtype=np.uint8)
    count = 0
    mod = "cnn" if hasattr(face_recognition, 'DLIB_USE_CUDA') and face_recognition.DLIB_USE_CUDA else "hog"
    for i, frame in enumerate(frames):
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        face_locations = face_recognition.face_locations(
            frame, number_of_times_to_upsample=0, model=mod
        )
        for face_location in face_locations:
            if count < len(frames):  # Check bounds before writing
                top, right, bottom, left = face_location
                face_image = frame[top:bottom, left:right]
                face_image = cv2.resize(face_image, (224, 224))
                temp_face[count] = face_image
                count += 1
            else:
                break  # Stop if we've filled the array
    return temp_face[:count], count
