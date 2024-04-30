# -*- coding: utf-8 -*-
"""Orgaextractor.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/github/tpark16/orgaextractor/blob/main/Orgaextractor.ipynb
"""

## requirements
import argparse

import os
import numpy as np
import cv2

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter

import random
import torchvision.transforms.functional as TF
from torchvision import transforms

import matplotlib.pyplot as plt
from tqdm import tqdm, trange
!pip install medpy
import medpy.metric.binary as bin
import pandas as pd

## We first want to load our dataset and convert it to numpy
"""
data file has to be in image format such as jpeg, png etc..
Not ready for numpy file yet.
A User only needs to change their dataset path in local and set result path.
YOU MUST EITHER DOWNLOAD OUR TEST DATA OR HAVE YOUR OWN.
"""

!gdown "1wOzvgroIgpEA9kaYfbz0Q3vUL5GY1my9&confirm=t" # Model weight file, takes about 20 secs, file will be stored under content
!mkdir result
!mkdir test
data_path = '/content/test'
result_dir = '/content/result'

## implement model
class Residual_block_3(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Residual_block_3, self).__init__()
        layers = []
        layers += [nn.Conv2d(in_channels=in_channels, out_channels=out_channels,
                                kernel_size=3, stride=1, padding=1,
                                bias=True)]
        layers += [nn.InstanceNorm2d(num_features=out_channels)]
        layers += [nn.ReLU()]
        layers += [nn.Conv2d(in_channels=out_channels, out_channels=out_channels,
                                kernel_size=3, stride=1, padding=1,
                                bias=True)]
        layers += [nn.InstanceNorm2d(num_features=out_channels)]
        layers += [nn.ReLU()]

        self.conv = nn.Sequential(*layers)

        skips = []
        skips += [nn.Conv2d(in_channels=in_channels, out_channels=out_channels,
                            kernel_size=3, stride=1, padding=1,
                            bias=True)]
        skips += [nn.InstanceNorm2d(num_features=out_channels)]

        self.skip = nn.Sequential(*skips)

    def forward(self, x):
        x = self.conv(x) + self.skip(x)
        return x


class Residual_block_7(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Residual_block_7, self).__init__()
        layers = []
        layers += [nn.Conv2d(in_channels=in_channels, out_channels=out_channels,
                                kernel_size=7, stride=1, padding=3,
                                bias=True)]
        layers += [nn.InstanceNorm2d(num_features=out_channels)]
        layers += [nn.ReLU()]
        layers += [nn.Conv2d(in_channels=out_channels, out_channels=out_channels,
                                kernel_size=7, stride=1, padding=3,
                                bias=True)]
        layers += [nn.InstanceNorm2d(num_features=out_channels)]
        layers += [nn.ReLU()]

        self.conv = nn.Sequential(*layers)

        skips = []
        skips += [nn.Conv2d(in_channels=in_channels, out_channels=out_channels,
                            kernel_size=7, stride=1, padding=3,
                            bias=True)]
        skips += [nn.InstanceNorm2d(num_features=out_channels)]

        self.skip = nn.Sequential(*skips)

    def forward(self, x):
        x = self.conv(x) + self.skip(x)
        return x


class Residual_block(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Residual_block, self).__init__()
        self.x3 = Residual_block_3(in_channels, out_channels)
        self.x7 = Residual_block_7(in_channels, out_channels)

        self.conv = nn.Conv2d(out_channels * 2, out_channels, kernel_size=1, stride=1, padding=0, bias=True)

    def forward(self, x):
        x3 = self.x3(x)
        x7 = self.x7(x)

        x = torch.cat((x3, x7), dim=1)
        x = self.conv(x)

        return x

class ResUNet_MS(nn.Module):
    def __init__(self):
        super(ResUNet_MS, self).__init__()

        self.pool = nn.MaxPool2d(kernel_size=2)

        self.enc1_1 = Residual_block(in_channels=1, out_channels=64)

        self.enc2_1 = Residual_block(in_channels=64, out_channels=128)

        self.enc3_1 = Residual_block(in_channels=128, out_channels=256)

        self.enc4_1 = Residual_block(in_channels=256, out_channels=512)

        self.enc5_1 = Residual_block(in_channels=512, out_channels=1024)

        self.unpool5 = nn.ConvTranspose2d(in_channels=1024, out_channels=512,
                                        kernel_size=2, stride=2, padding=0, bias=True)
        self.dec5_1 = Residual_block(in_channels=1024, out_channels=512)

        self.unpool4 = nn.ConvTranspose2d(in_channels=512, out_channels=256,
                                          kernel_size=2, stride=2, padding=0, bias=True)
        self.dec4_1 = Residual_block(in_channels=512, out_channels=256)

        self.unpool3 = nn.ConvTranspose2d(in_channels=256, out_channels=128,
                                          kernel_size=2, stride=2, padding=0, bias=True)
        self.dec3_1 = Residual_block(in_channels=256, out_channels=128)

        self.unpool2 = nn.ConvTranspose2d(in_channels=128, out_channels=64,
                                          kernel_size=2, stride=2, padding=0, bias=True)
        self.dec2_1 = Residual_block(in_channels=128, out_channels=64)


        self.fc = nn.Conv2d(in_channels=64, out_channels=1, kernel_size=1, stride=1, padding=0, bias=True)

    def forward(self, x):
        enc1_1 = self.enc1_1(x)

        pool2 = self.pool(enc1_1)
        enc2_1 = self.enc2_1(pool2)

        pool3 = self.pool(enc2_1)
        enc3_1 = self.enc3_1(pool3)

        pool4 = self.pool(enc3_1)
        enc4_1 = self.enc4_1(pool4)

        pool5 = self.pool(enc4_1)
        enc5_1 = self.enc5_1(pool5)

        unpool5 = self.unpool5(enc5_1)
        cat5 = torch.cat((unpool5, enc4_1), dim=1)
        dec5_1 = self.dec5_1(cat5)

        unpool4 = self.unpool4(dec5_1)
        cat4 = torch.cat((unpool4, enc3_1), dim=1)
        dec4_1 = self.dec4_1(cat4)

        unpool3 = self.unpool3(dec4_1)
        cat3 = torch.cat((unpool3, enc2_1), dim=1)
        dec3_1 = self.dec3_1(cat3)

        unpool2 = self.unpool2(dec3_1)
        cat2 = torch.cat((unpool2, enc1_1), dim=1)
        dec2_1 = self.dec2_1(cat2)

        x = self.fc(dec2_1)

        return x

## we would have to transform data if image size is too large
class Dataset(torch.utils.data.Dataset):
    def __init__(self, data_dir):
        self.data_dir = data_dir

        lst_data = os.listdir(self.data_dir)

        lst_input = [f for f in lst_data if f.startswith('input')]

        lst_input.sort()

        self.lst_input = lst_input

    def __len__(self):
        return len(self.lst_input)

    # for test
    def test_transform(self, image):
        # Transform to tensor
        image = TF.to_tensor(image)

        image = TF.normalize(image, 0.5, 0.5)

        return image


    def __getitem__(self, index):

        p = os.path.join(self.data_dir, self.lst_input[index])

        if p.endswith('npy'):
          input = np.load(p)
        else:
          input = cv2.imread(os.path.join(self.data_dir, self.lst_input[index]), 0)

        input = input/255.0

        if input.ndim == 2:
            input = input[:, :, np.newaxis]

        # resize
        # input = cv2.resize(input, (512,512), interpolation=cv2.INTER_AREA)

        input = self.test_transform(input)

        return input

## pp
def draw_contour(args: np.ndarray):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7,7))

    pred= args

    pred = pred // 255

    # erase metric bar
    pred[1080:, 1400:] = 0

    o = np.uint8(pred)
    contours, hie= cv2.findContours(o, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    r = cv2.fillPoly(o, pts=contours, color=(255,255,255))

    o = cv2.morphologyEx(r, cv2.MORPH_OPEN, kernel, iterations=2)

    pp = o

    o = np.uint8(o//255)

    contours, hie= cv2.findContours(o, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    img_contour = cv2.drawContours(o, contours, -1, color=(255, 255, 255), thickness=5)

    return img_contour, contours, hie, pp



def analysis(img_contour, contours, hie):
    info = {}
    c = contours
    c_im = img_contour
    for i, x in enumerate(c):
        tmp = {}
        M = cv2.moments(x)

        area = M['m00']
        if area == 0.0:
            continue

        cX = int(M['m10'] / M['m00'])
        cY = int(M['m01'] / M['m00'])


        _,radius = cv2.minEnclosingCircle(x)
        _, (minorAxisLength, majorAxisLength), angle = cv2.fitEllipse(x)

        a = majorAxisLength / 2
        b = minorAxisLength / 2

        Eccentricity = round(np.sqrt(pow(a, 2) - pow(b, 2))/a, 2)

        radius = int(radius)
        diameter_in_pixels = radius * 2

        cv2.putText(c_im, text=str(i+1), org=(cX, cY), fontFace= cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.5, color=(255,255,255),
                thickness=1, lineType=cv2.LINE_AA)
        tmp["Area"] = area
        tmp["Diameter"] = diameter_in_pixels
        tmp["majorAxisLength"] = np.round(majorAxisLength, 2)
        tmp["minorAxisLength"] = np.round(minorAxisLength,2)
        tmp["Eccentricity"] = Eccentricity
        tmp["Perimeter"] = np.round(cv2.arcLength(x, True),2)
        info[i+1] = tmp


    return info, c_im

## define parameters
## pretrained_model = final_model.pth
# pretrained_model = torch.load('/content/drive/Shareddrives/오가노이드_AI_영상/organoid/chk/final_model.pth')

device = 'cuda'
pretrained_model = torch.load('/content/orgaextractor.pth')

model = ResUNet_MS().to(device)
model = nn.DataParallel(module=model).to(device)
model.load_state_dict(pretrained_model)
# model.load_state_dict(pretrained_model['optim'], strict=False)

batch_size = 2

fn_tonumpy = lambda x: x.to('cpu').detach().numpy().transpose(0, 2, 3, 1)
fn_denorm = lambda x, mean, std: (x * std) + mean
fn_class = lambda x: 1.0 * (x > 0.5)

## dataloader
dataset_test = Dataset(data_dir=data_path)
loader_test = DataLoader(dataset_test, batch_size=batch_size, shuffle=False)
num_data_test = len(dataset_test)
num_batch_test = np.ceil(num_data_test / batch_size)

## inference

from torch.cuda.amp import autocast, GradScaler
amp_grad_scaler = GradScaler()

# create result folder if not exists
if not os.path.exists(os.path.join(result_dir, 'png')):
        os.mkdir(os.path.join(result_dir, 'png'))
        os.mkdir(os.path.join(result_dir, 'numpy'))

# Setting Excel writer
path = os.path.join(result_dir, 'analysis.xlsx')
writer = pd.ExcelWriter(path, engine = 'openpyxl')

with torch.no_grad():
      model.eval()
      # loss_arr = []
      for batch, data in enumerate(loader_test, 1):
      # for data in loader_test:
          input = data.to(device, dtype=torch.float)
          # label = data[1].to(device, dtype=torch.float)

          with autocast():
            output = model(input)

          # label = fn_tonumpy(label)
          input = fn_tonumpy(fn_denorm(input, mean=0.5, std=0.5))
          output = fn_tonumpy(fn_class(output))

          for j in range(input.shape[0]):

              id = batch_size * (batch - 1) + j

              # plt.imsave(os.path.join(result_dir, 'png', f'label_{id}.png'), label[j].squeeze(), cmap='gray')
              plt.imsave(os.path.join(result_dir, 'png', f'input_{id}.png'), input[j].squeeze(), cmap='gray')
              plt.imsave(os.path.join(result_dir, 'png', f'output_{id}.png'), output[j].squeeze(), cmap='gray')

              # reread output due to cv2 type
              o = os.path.join(result_dir, 'png', f'output_{id}.png')
              o = cv2.imread(o, 0)
              img_contour, contour, hie, pp = draw_contour(o)
              info, c_im = analysis(img_contour, contour, hie)
              df = pd.DataFrame(info)
              df_t = df.transpose()
              df_t.to_excel(writer, sheet_name=f'contour_{id}')
              # print(c_im.shape)
              plt.imsave(os.path.join(result_dir, 'png', f'contour_{id}.png'), img_contour, cmap='gray')
              plt.imsave(os.path.join(result_dir, 'png', f'pp_{id}.png'), pp, cmap='gray')

              # np.save(os.path.join(result_dir, 'numpy', f'label_{id}.npy'), label[j].squeeze())
              np.save(os.path.join(result_dir, 'numpy', f'input_{id}.npy'), input[j].squeeze())
              np.save(os.path.join(result_dir, 'numpy', f'output_{id}.npy'), output[j].squeeze())
          writer.save()

print('Image saved at: ', os.path.join(result_dir, 'png'))
print('Numpy file saved at: ', os.path.join(result_dir, 'numpy'))
print('--------------Orgaextractor--------------')