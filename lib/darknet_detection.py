# python3 object_detection.py --input=test.jpg --model=/src/app/bin/yolov3.weights --config=/src/app/cfg/yolov3-tiny.cfg --classes=/src/app/cfg/coco.names --scale=0.00392 --width=416 --height=416
# https://github.com/iArunava/YOLOv3-Object-Detection-with-OpenCV
import logging
import argparse
import time

import cv2 as cv
import numpy as np
from lib.helpers import calculate_relative_coords

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    def __init__(self, input, model, config, classes, thr, nms, model_res):
        self.input = input
        self.confThreshold = thr
        self.nmsThreshold = nms
        self.model_res = model_res

        # Activate OpenCL
        if cv.ocl.haveOpenCL():
            cv.ocl.setUseOpenCL(True)

        # Load classes into memory
        self.load_classes(classes)

        # Load and initialize network
        self.load_network(model, config)

    def load_classes(self, classes):
        # Load names of classes
        self.classes = None
        if classes:
            with open(classes, "rt") as f:
                self.classes = f.read().rstrip("\n").split("\n")

    def load_network(self, model, config):
        # Load a network
        self.net = cv.dnn.readNet(model, config, "darknet")
        # self.net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
        # self.net.setPreferableTarget(cv.dnn.DNN_TARGET_OPENCL)
        self.net.setPreferableBackend(cv.dnn.DNN_BACKEND_CUDA)
        self.net.setPreferableTarget(cv.dnn.DNN_TARGET_CUDA)

    def getOutputsNames(self, net):
        layersNames = net.getLayerNames()
        return [layersNames[i[0] - 1] for i in net.getUnconnectedOutLayers()]

    def postprocess(self, outs):
        classIds = []
        confidences = []
        boxes = []
        for out in outs:
            for detection in out:
                scores = detection[5:]
                classId = np.argmax(scores)
                confidence = scores[classId]
                if confidence > self.confThreshold:
                    center_x = int(detection[0] * self.model_res[0])
                    center_y = int(detection[1] * self.model_res[1])
                    width = int(detection[2] * self.model_res[0])
                    height = int(detection[3] * self.model_res[1])
                    left = int(center_x - width / 2)
                    top = int(center_y - height / 2)
                    classIds.append(classId)
                    confidences.append(float(confidence))
                    boxes.append([left, top, width, height])

        indices = cv.dnn.NMSBoxes(
            boxes, confidences, self.confThreshold, self.nmsThreshold
        )

        detections = list()

        for i in indices:
            i = i[0]
            box = boxes[i]
            left = box[0]
            top = box[1]
            width = box[2]
            height = box[3]

            if self.classes:
                label = self.classes[classIds[i]]

            relative_coords = calculate_relative_coords(
                (left, top, left + width, top + height), self.model_res
            )

            detections.append(
                {
                    "label": label if label else "Unknown",
                    "confidence": round(confidences[i], 3),
                    "height": round(relative_coords[3] - relative_coords[1], 3),
                    "width": round(relative_coords[2] - relative_coords[0], 3),
                    "relative_x1": round(relative_coords[0], 3),
                    "relative_y1": round(relative_coords[1], 3),
                    "relative_x2": round(relative_coords[2], 3),
                    "relative_y2": round(relative_coords[3], 3),
                }
            )

        return detections

    def return_objects(self, frame):
        # Create a 4D blob from a frame.
        inpWidth = 320
        inpHeight = 320
        blob = cv.dnn.blobFromImage(
            frame, 0.00392, (inpWidth, inpHeight), [0, 0, 0], True, crop=False
        )

        # Run a model
        self.net.setInput(blob)
        outs = self.net.forward(self.getOutputsNames(self.net))

        objects = self.postprocess(outs)

        return objects


def parse_args():
    parser = argparse.ArgumentParser(
        description="Use this script to run object detection deep learning networks using OpenCV."
    )
    parser.add_argument(
        "--input",
        help="Path to input image or video file. Skip this argument to capture frames from a camera.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Path to a binary file of model contains trained weights. "
        "It could be a file with extensions .caffemodel (Caffe), "
        ".pb (TensorFlow), .t7 or .net (Torch), .weights (Darknet), .bin (OpenVINO)",
    )
    parser.add_argument(
        "--config",
        help="Path to a text file of model contains network configuration. "
        "It could be a file with extensions .prototxt (Caffe), .pbtxt or .config (TensorFlow), .cfg (Darknet), .xml (OpenVINO)",
    )
    parser.add_argument(
        "--classes",
        help="Optional path to a text file with names of classes to label detected objects.",
    )
    parser.add_argument("--thr", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument(
        "--nms", type=float, default=0.4, help="Non-maximum suppression threshold"
    )
    args = parser.parse_args()

    return args.input, args.model, args.config, args.classes, args.thr, args.nms


def main(input, model, config, classes, thr, nms):
    colors = [tuple(255 * np.random.rand(3)) for _ in range(10)]
    od = ObjectDetection(input, model, config, classes, thr, nms)
    cap = cv.VideoCapture(input if input else 0)
    while True:
        stime = time.time()
        cap.open(input)
        hasFrame, frame = cap.read()
        if not hasFrame:
            print("no frame, Exiting")
            exit()

        results = od.return_objects(frame)

        for color, result in zip(colors, results):
            tl = (result["x1"], result["y1"])
            br = (result["x2"], result["y2"])
            label = result["label"]
            confidence = result["confidence"]
            text = "{}: {:.0f}%".format(label, confidence * 100)
            frame = cv.rectangle(frame, tl, br, color, 5)
            frame = cv.putText(
                frame, text, tl, cv.FONT_HERSHEY_COMPLEX, 1, (0, 0, 0), 2
            )
        print("FPS {:.1f}".format(1 / (time.time() - stime)))
        cv.imwrite("/src/app/out_test.jpg", frame)
    return


if __name__ == "__main__":
    main(*parse_args())
