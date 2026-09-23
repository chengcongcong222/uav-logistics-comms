import pandas as pd
b = pd.read_csv("/home/ccc/projects/uav-logistics-comms/data/processed/boxes.csv")
print(b.groupby("service_id").size().sort_values(ascending=False))
print("max", b.groupby("service_id").size().max())
