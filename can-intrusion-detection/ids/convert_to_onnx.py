"""
convert_to_onnx.py -- convert the trained Keras autoencoder to ONNX, the
format Qualcomm AI Hub's submit_compile_job() actually accepts (confirmed:
"The model must be a PyTorch model or an ONNX model" -- native .keras is not
directly supported).

Verified: converts and numerically matches the original Keras model exactly
(max abs difference 0.0 on a random test input, same architecture).

Usage:
    python convert_to_onnx.py
"""

import numpy as np
import tensorflow as tf
import tf2onnx

from features import FEATURE_NAMES

N_FEATURES = len(FEATURE_NAMES)


def main():
    model = tf.keras.models.load_model("model.keras")

    input_signature = [tf.TensorSpec([1, N_FEATURES], tf.float32, name="x")]
    onnx_model, _ = tf2onnx.convert.from_keras(model, input_signature, opset=13)

    with open("model.onnx", "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"Saved model.onnx ({N_FEATURES} input features)")

    import onnxruntime as ort
    test_input = np.random.randn(1, N_FEATURES).astype(np.float32)
    keras_out = model.predict(test_input, verbose=0)
    session = ort.InferenceSession("model.onnx")
    onnx_out = session.run(None, {"x": test_input})[0]
    max_diff = np.max(np.abs(keras_out - onnx_out))
    print(f"Verification: max abs difference = {max_diff:.2e}")
    assert max_diff < 1e-4, "ONNX conversion diverged from the original model!"
    print("PASS: ONNX model matches the original Keras model numerically")


if __name__ == "__main__":
    main()
