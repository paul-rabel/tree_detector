import torch
import torchvision
from torchvision.models.detection import fasterrcnn_resnet50_fpn

# Check MPS is available (Apple Silicon GPU)
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

# Load pretrained Faster R-CNN
model = fasterrcnn_resnet50_fpn(weights="DEFAULT")
model.to(device)
model.eval()