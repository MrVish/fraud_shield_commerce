"""
Training script for XGBoost fraud detection model.
Usage: python -m app.scoring.train --data path/to/train.csv --output models/fraud_model_v1.joblib
"""
import argparse
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report


def train_model(data_path: str, output_path: str):
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    target_col = "isFraud"
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found.")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols.remove(target_col)
    if "TransactionID" in numeric_cols:
        numeric_cols.remove("TransactionID")
    feature_cols = numeric_cols[:30]

    X = df[feature_cols].fillna(0)
    y = df[target_col]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print(f"Training on {len(X_train)} samples, testing on {len(X_test)}")
    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1),
        random_state=42, eval_metric="auc",
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=True)

    y_pred = model.predict(X_test)
    print(f"\nAccuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred):.4f}")
    print(f"F1: {f1_score(y_test, y_pred):.4f}")

    joblib.dump(model, output_path)
    print(f"Model saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="models/fraud_model_v1.joblib")
    args = parser.parse_args()
    train_model(args.data, args.output)
