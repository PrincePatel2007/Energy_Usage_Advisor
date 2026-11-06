import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

df = pd.read_csv("Datasets/hostel_energy_dataset_3months.csv", parse_dates=["timestamp"]).set_index("timestamp")
app = ["lighting_kwh","ceiling_fans_kwh","air_conditioners_kwh","water_heaters_kwh","kitchen_mess_kwh",
       "refrigeration_water_cooler_kwh","laundry_machines_kwh","electronics_wifi_kwh","water_pumps_kwh","common_areas_kwh"]

# 1) STANDARDISE then PCA
X = StandardScaler().fit_transform(df[app])
pca = PCA().fit(X)
cum = pca.explained_variance_ratio_.cumsum()
print("Cumulative variance explained:", np.round(cum[:5], 3))
n_comp = int(np.argmax(cum >= 0.80) + 1)
print("Components kept (>=80% variance):", n_comp)
Z = PCA(n_components=n_comp, random_state=0).fit_transform(X)
load = pd.DataFrame(PCA(n_components=2).fit(X).components_.T, index=app, columns=["PC1","PC2"]).round(2)
print("\nPC loadings:\n", load.to_string())

# 2) K-MEANS: choose k by silhouette
scores = {}
for k in range(3, 7):
    scores[k] = silhouette_score(Z, KMeans(k, n_init=10, random_state=0).fit_predict(Z))
print("\nSilhouette by k:", {k: round(v,3) for k,v in scores.items()})
best_k = max(scores, key=scores.get)
df["cluster"] = KMeans(best_k, n_init=10, random_state=0).fit_predict(Z)
print("Chosen k:", best_k)

# 3) PROFILE EACH CLUSTER (use this to name them)
prof = df.groupby("cluster").agg(slots=("cluster","size"), mean_hour=("hour","mean"),
    total_kwh=("total_consumption_kwh","mean"), ac=("air_conditioners_kwh","mean"),
    mess=("kitchen_mess_kwh","mean"), geyser=("water_heaters_kwh","mean"),
    laundry=("laundry_machines_kwh","mean"), elec=("electronics_wifi_kwh","mean"),
    occ=("occupancy_pct","mean"), solar=("solar_generation_kwh","mean"),
    peak_share=("tariff_period", lambda s: (s=="peak").mean())).round(2)
print("\nCluster profiles:\n", prof.to_string())

# 4) PLOTS
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
sc = ax[0].scatter(Z[:,0], Z[:,1], c=df.cluster, cmap="tab10", s=8)
ax[0].set(xlabel="PC1", ylabel="PC2", title=f"PCA view of time slots (k={best_k})")
ax[0].legend(*sc.legend_elements(), title="cluster")
mix = pd.crosstab(df.index.hour, df.cluster, normalize="index")
mix.plot(kind="bar", stacked=True, ax=ax[1], colormap="tab10", width=0.9, legend=False)
ax[1].set(xlabel="hour of day", ylabel="share of slots", title="Which cluster at which hour")
plt.tight_layout(); plt.savefig("clusters.png", dpi=130)
df[["cluster"]].to_csv("cluster_labels.csv")
