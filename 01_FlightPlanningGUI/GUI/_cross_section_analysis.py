import cv2
import numpy as np
import math
from matplotlib import pyplot as plt



def process_crosssection_image(crosssection_dir, input_scale_meters, epsilon_factor):
    # Constants for HSV range
    lower_green_hsv = np.array([40, 50, 50])
    upper_green_hsv = np.array([80, 255, 255])
    lower_blue_hsv = np.array([100, 50, 50])
    upper_blue_hsv = np.array([140, 255, 255])

    
    
    image = cv2.imread(crosssection_dir)
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    blue_mask = cv2.inRange(hsv_image, lower_blue_hsv, upper_blue_hsv)
    green_mask = cv2.inRange(hsv_image, lower_green_hsv, upper_green_hsv)

    contours_green, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    scale_line_contour = max(contours_green, key=lambda c: cv2.arcLength(c, False))

    rect = cv2.minAreaRect(scale_line_contour)
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    width = np.linalg.norm(box[0] - box[1])
    height = np.linalg.norm(box[1] - box[2])
    scale_length_pixels = max(width, height)
    pixel_to_meter_ratio = input_scale_meters / scale_length_pixels

    contours_blue, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cross_section_contour = max(contours_blue, key=cv2.contourArea)

    epsilon = epsilon_factor * cv2.arcLength(cross_section_contour, True)
    approx_polygon = cv2.approxPolyDP(cross_section_contour, epsilon, True)

    distances = []
    for i in range(len(approx_polygon)):
        point1 = approx_polygon[i][0]
        point2 = approx_polygon[(i + 1) % len(approx_polygon)][0]
        cv2.line(image, tuple(point1), tuple(point2), (0, 0, 255), 2)  # Draw red line

        distance = np.linalg.norm(point1 - point2) * pixel_to_meter_ratio
        distances.append(distance)

        midpoint_segment = ((point1[0] + point2[0]) // 2, (point1[1] + point2[1]) // 2)
        cv2.putText(image, f"{distance:.2f} m", midpoint_segment, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    transformed_points = []
    mid_x = image.shape[1] // 2
    top_y = np.min(approx_polygon[:, 0, 1])
    midpoint = np.array([mid_x, top_y])

    # Transform the coordinates of the contour points and print them
    transformed_points = np.zeros((len(approx_polygon), 3))  # Initialize an array for transformed points
    
    for i, point in enumerate(approx_polygon):
        # Transform points: X = 0, Y = horizontal distance from the midpoint, Z = vertical distance from the midpoint
        transformed_points[i] = [0, (point[0][0] - midpoint[0]) * pixel_to_meter_ratio, (point[0][1] - midpoint[1]) * pixel_to_meter_ratio]
        

    # slab_height = max(transformed_y) - min(transformed_y)
    # measurements = {
    #     'distances': distances,
    #     'slab_height': slab_height,
    #     'max_width': calculate_maximum_width(transformed_points)
    # }

    return image, transformed_points
    #return image, transformed_points

def calculate_maximum_width(points):
    max_distance = 0
    for i, point1 in enumerate(points):
        for point2 in points[i + 1:]:
            distance = math.sqrt((point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)
            max_distance = max(max_distance, distance)
    return max_distance

