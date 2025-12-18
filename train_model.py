import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.optimizers import Adam
import pickle  # ✅ NEW: for saving training history

TRAIN_DIR = "dataset/Drowsy_datset/train"
VAL_DIR = "dataset/Drowsy_datset/test"
IMG_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 10

# Data Augmentation
datagen = ImageDataGenerator(
    rescale=1.0/255,
    rotation_range=15,
    zoom_range=0.2,
    horizontal_flip=True,
)

train_gen = datagen.flow_from_directory(
    TRAIN_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="binary"
)

val_gen = datagen.flow_from_directory(
    VAL_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="binary"
)

# Load Pretrained MobileNetV2
base_model = MobileNetV2(weights="imagenet", include_top=False, input_shape=(224, 224, 3))
for layer in base_model.layers:
    layer.trainable = False

x = GlobalAveragePooling2D()(base_model.output)
x = Dropout(0.3)(x)
x = Dense(128, activation="relu")(x)
x = Dropout(0.3)(x)
output = Dense(1, activation="sigmoid")(x)

model = Model(inputs=base_model.input, outputs=output)
model.compile(optimizer=Adam(1e-4), loss="binary_crossentropy", metrics=["accuracy"])

# Train
history = model.fit(train_gen, validation_data=val_gen, epochs=EPOCHS)

# Save model
model.save("model.h5")
print("✅ Model trained and saved as model.h5")

# ✅ Save training history
with open("history.pkl", "wb") as f:
    pickle.dump(history.history, f)
print("📈 Training history saved as history.pkl")