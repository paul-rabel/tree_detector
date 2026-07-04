from PIL import Image, ImageDraw
import torch
from torchvision.models.detection import fasterrcnn_resnet50_fpn
import torchvision.transforms as T
from pathlib import Path # to iterate over images
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

# To get weights.pt
from pathlib import Path
WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.pt"
TEST_IMAGES_PATH = Path(__file__).resolve().parent / "test_images"

device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Running on {device}")

def load_model() -> torch.nn.Module:
    # Load pretrained Faster R-CNN
    model = fasterrcnn_resnet50_fpn(weights=None)
    num_classes = 2  # 1 class (tree) + background
    # get number of input features for the classifier (from the conv. layers / pooling)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    # replace the pre-trained head with a new one
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    model.load_state_dict(torch.load(WEIGHTS_PATH, weights_only=True))
    model.to(device)
    return model

def visualize(image_path, predictions, threshold):
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    boxes = predictions[0]["boxes"]
    scores = predictions[0]["scores"]
    for box, score in zip(boxes, scores):
        if score > threshold:
            box = box.cpu().tolist()
            draw.rectangle(box, outline="green", width=2)
            center_x = (box[2] - box[0]) / 2 + box[0]
            center_y = (box[3] - box[1]) / 2 + box[1]
            draw.ellipse((center_x - 5, center_y - 5, center_x + 5, center_y + 5), fill="red")

    img.show()

def inference(file_path, model):
    img = Image.open(file_path).convert("RGB")

    # Convert img to tensor (what the model expects)
    transform = T.ToTensor()
    img_tensor = transform(img).to(device)

    model.eval()
    with torch.no_grad():
        predictions = model([img_tensor])
    return predictions

def main():
    model = load_model()
    for filepath in Path(TEST_IMAGES_PATH).iterdir():
        predictions = inference(filepath, model)
        visualize(filepath, predictions, 0.5)


if __name__ == "__main__":
    main()