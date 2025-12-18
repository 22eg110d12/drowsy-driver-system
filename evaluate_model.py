# evaluate_model.py
import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import classification_report, confusion_matrix

# === Paths ===
BASE_DIR = r"C:\Users\godal\OneDrive\Desktop\miniiiiiii\Drowsy-driver\dataset\Drowsy_datset"
TEST_DIR = os.path.join(BASE_DIR, "test")

# === Load Model ===
model = load_model("model.h5")  # or "model.keras" if you saved in new format

# === Prepare Data ===
test_datagen = ImageDataGenerator(rescale=1.0 / 255)
test_gen = test_datagen.flow_from_directory(
    TEST_DIR,
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary",
    shuffle=False
)

# === Evaluate ===
loss, acc = model.evaluate(test_gen)
print(f"\n✅ Test Accuracy: {acc * 100:.2f}%")

# === Predictions ===
y_pred = (model.predict(test_gen) > 0.5).astype("int32")
y_true = test_gen.classes

# === Reports ===
print("\n📊 Classification Report:")
print(classification_report(y_true, y_pred, target_names=list(test_gen.class_indices.keys())))

print("\n🧩 Confusion Matrix:")
print(confusion_matrix(y_true, y_pred))
