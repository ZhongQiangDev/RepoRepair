import os
from tqdm import tqdm
from PIL import Image
import shutil
import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim


def calculate_frame_difference(frame1, frame2):
    frame1_rgb = frame1.convert("RGB")
    frame2_rgb = frame2.convert("RGB")
    diff = np.mean(np.abs(np.array(frame1_rgb) - np.array(frame2_rgb)))
    return diff


def calculate_ssim_rgb(frame1, frame2):
    """
    计算两帧 RGB 图像之间的结构相似性指数 (SSIM)
    """
    # 确保输入是 RGB 图像
    if len(frame1.shape) != 3 or frame1.shape[2] != 3:
        raise ValueError("输入图像必须是 RGB 图像")
    if len(frame2.shape) != 3 or frame2.shape[2] != 3:
        raise ValueError("输入图像必须是 RGB 图像")

    # 计算多通道 SSIM
    score, diff = ssim(frame1, frame2, full=True, multichannel=True, channel_axis=2)
    return score, diff


def compare_frames_rgb(frame1, frame2):
    """
    比较两帧 RGB 图像的 SSIM，并根据阈值输出结果
    """
    score, diff = calculate_ssim_rgb(frame1, frame2)
    return score, diff


def slice_gif_with_keyframes(gif_path, output_folder, difference_threshold=0.995):
    gif = Image.open(gif_path)
    gif_name = os.path.basename(gif_path)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    frame_number = 0
    saved_frame_number = 0
    last_saved_frame = None  # 上一次保存的帧
    total_frames = 0  # 总帧数

    try:
        while True:
            gif.seek(frame_number)
            total_frames += 1
            frame_number += 1
    except EOFError:
        pass

    frame_number = 0
    gif.seek(0)

    try:
        while True:
            current_frame = gif.copy()

            if frame_number == 0:
                current_frame.save(os.path.join(output_folder, f"{gif_name}_{saved_frame_number}.png"), "PNG")
                last_saved_frame = current_frame
                saved_frame_number += 1
            else:
                if last_saved_frame is not None:
                    score, diff = compare_frames_rgb(np.array(last_saved_frame.convert("RGB")), np.array(current_frame.convert("RGB")))
                    # diff = calculate_frame_difference(last_saved_frame, current_frame)
                    if score < difference_threshold:
                        current_frame.save(os.path.join(output_folder, f"{gif_name}_{saved_frame_number}.png"), "PNG")
                        last_saved_frame = current_frame
                        saved_frame_number += 1
            # 移动到下一帧
            frame_number += 2
            gif.seek(frame_number)
    except EOFError:
        pass
    print(f"{gif_name}切片完成，共保存 {saved_frame_number}/{total_frames} 帧，保存到 {output_folder}")

    # if os.path.exists(output_folder):
    #     shutil.rmtree(output_folder)


def find_gif_files(folder_path):
    gif_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".gif"):
                full_path = os.path.join(root, file)
                gif_files.append(full_path)
    return gif_files


if __name__ == '__main__':
    gif_files = find_gif_files('pic')
    for gif in gif_files:
        slice_gif_with_keyframes(gif, os.path.join(os.path.dirname(gif), 'gif_key'))
