import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend

import matplotlib.pyplot as plt
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns
import pickle

# === Paths ===
TEST_DIR = "dataset/Drowsy_datset/test"
MODEL_PATH = "model.h5"
HISTORY_PATH = "history.pkl"

# === Load model ===
model = load_model(MODEL_PATH)

# === Prepare test data ===
datagen = ImageDataGenerator(rescale=1.0/255)
test_gen = datagen.flow_from_directory(
    TEST_DIR,
    target_size=(224, 224),
    batch_size=16,
    class_mode="binary",
    shuffle=False
)

# === Evaluate the model ===
loss, acc = model.evaluate(test_gen)
print(f"\n✅ Test Accuracy: {acc * 100:.2f}%")

# === Predictions ===
y_pred = (model.predict(test_gen) > 0.5).astype("int32")
y_true = test_gen.classes

# === Classification Report ===
print("\n📊 Classification Report:")
print(classification_report(y_true, y_pred, target_names=list(test_gen.class_indices.keys())))

# === Confusion Matrix ===
cm = confusion_matrix(y_true, y_pred)
plt.figure(figsize=(5, 4))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=test_gen.class_indices.keys(),
            yticklabels=test_gen.class_indices.keys())
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Confusion Matrix")
plt.tight_layout()
plt.savefig("confusion_matrix_real.png")

# === Accuracy and Loss Graphs from history ===
try:
    with open(HISTORY_PATH, "rb") as f:
        history_data = pickle.load(f)

    # Accuracy plot
    plt.figure(figsize=(6, 4))
    plt.plot(history_data['accuracy'], label='Training Accuracy')
    plt.plot(history_data['val_accuracy'], label='Validation Accuracy')
    plt.xlabel('Epochs')
    plt.ylabel('Accuracy')
    plt.title('Training vs Validation Accuracy')
    plt.legend()
    plt.tight_layout()
    plt.savefig("accuracy_curve_real.png")

    # Loss plot
    plt.figure(figsize=(6, 4))
    plt.plot(history_data['loss'], label='Training Loss')
    plt.plot(history_data['val_loss'], label='Validation Loss')
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.title('Training vs Validation Loss')
    plt.legend()
    plt.tight_layout()
    plt.savefig("loss_curve_real.png")

except FileNotFoundError:
    print("\n⚠️ 'history.pkl' not found. Rerun training with 'history = model.fit(...)' and save it using pickle.")