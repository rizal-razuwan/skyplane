import subprocess
import os
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm.notebook import tqdm
import seaborn as sns
import streamlit as st
from skylark import skylark_root

data_dir = skylark_root / "data"
figure_dir = data_dir / "figures" / "pareto_speedups_updated"
figure_dir.mkdir(exist_ok=True, parents=True)

plt.style.use("seaborn-bright")
plt.set_cmap("plasma")

out_fname = data_dir / "pareto_data.df.parquet"
source_bucket_path = st.text_input("S3 bucket prefix", "s3://skylark-optimizer-results/pareto_data")
source_bucket_experiment_tag = st.text_input("Experiment tag", "2022.02.01_00.07_e86e33b2-bccf-4509-80e4-1f2ac62d7c54")
st.button("Recompute dataframe", on_click=lambda: Path(out_fname).unlink(missing_ok=True))

def download_and_parse_data(out_fname):
    out_dir = data_dir / 'pareto_raw_data' / source_bucket_experiment_tag
    if not out_fname.exists():
        st.info("Parsing data, this will take some time...")
        s3_path = os.path.join(source_bucket_path, source_bucket_experiment_tag)
        st.info(f"aws s3 sync {s3_path} {out_dir}")
        with st.spinner("Downloading data..."):
            subprocess.run(f"aws s3 sync {s3_path} {out_dir}", shell=True)
        
        rows = []
        for file in out_dir.glob("*.pkl"):
            with st.spinner(f"Parsing {file.name}..."):
                with open(file, "rb") as f:
                    for i in pickle.load(f):
                        x = i.__dict__.copy()
                        for k, v in x['problem'].__dict__.items():
                            x[f"problem_{k}"] = v
                        del x['problem']
                        rows.append(x)
        df = pd.DataFrame(rows)
        st.info(f"Saving data to {out_fname}, has {len(df)} rows")
        df = df.drop(columns=["var_edge_flow_gigabits", "var_conn", "var_instances_per_region", "cost_egress_by_edge"])
        df.to_parquet(out_fname)
    return pd.read_parquet(out_fname)

def parse_data(df):
    df = df.drop(columns=["problem_const_throughput_grid_gbits", "problem_const_cost_per_gb_grid", "extra_data"])
    df = df[df.is_feasible].dropna()
    df['throughput_achieved_gbits'] = df['throughput_achieved_gbits'].apply(lambda x: x[0])
    df["problem_src_region"] = df["problem_src"].apply(lambda x: x.split("-")[0])
    df["problem_dst_region"] = df["problem_dst"].apply(lambda x: x.split("-")[0])
    return df

df = parse_data(download_and_parse_data(out_fname))

# select rows where throughput_achieved_gbits >= baseline_throughput_gbits
# df = df[df["throughput_achieved_gbits"] >= df["baseline_achieved_throughput_gbits"]]

src_regions_choices = sorted(df["problem_src"].unique())
dst_regions_choices = sorted(df["problem_dst"].unique())
instance_choices = sorted(df["problem_instance_limit"].unique())

########
# Plot geomean
########

# for each src, dest pair, compute the geometric mean of throughput speedup
# def calc_geomean(x):
#     if len(x) == 0:
#         return np.nan
#     return np.exp(np.mean(np.log(x)))

# st.write("Geomean speedup")
# fig, ax = plt.subplots(figsize=(8, 6))
# for (src_region, dst_region), df_grouped in df.groupby(["problem_src", "problem_dst"]):
#     df_grouped["throughput_speedup"] = df_grouped["throughput_achieved_gbits"] / df_grouped["baseline_throughput_achieved_gbits"]
#     df_grouped["cost_increase"] = df_grouped["cost_total"] / min(df_grouped["cost_total"])
#     df_grouped = df_grouped[df_grouped["throughput_speedup"] > 1]
#     df_grouped.sort_values(by="throughput_speedup", inplace=True)

#     x = df_grouped["throughput_speedup"]
#     y = df_grouped["cost_increase"]
#     # add (1, 1)
#     x = [1] + list(x)
#     y = [1] + list(y)
#     label = "{} to {}".format(src_region, dst_region)
#     ax.plot(x, y, label=label, alpha=0.8)
# ax.set_xlabel("Throughput speedup (x)")
# ax.set_ylabel("Cost increase (x)")
# fig.set_facecolor("white")
# st.pyplot(fig, bbox_inches="tight")

########
# Filter results to a single src, dest pair
########

st.subheader("Filter by source region")
st.write(f"Sources: {', '.join(src_regions_choices)}")
src_prefix = st.text_input("Source region prefix", "")
st.subheader("Filter by destination region")
dst_prefix = st.text_input("Destination region prefix", "")
st.subheader("Filter by instance limit")
instance_limit = st.selectbox("Instance limit", instance_choices)

df = df[df["problem_src"].str.startswith(src_prefix)]
df = df[df["problem_dst"].str.startswith(dst_prefix)]
df = df[df["problem_instance_limit"] == instance_limit]
st.info(f"Filtered to {len(df)} rows")

if len(df) > 10000:
    st.warning("Too many rows to plot. Only plotting the first 10000.")
    df = df.iloc[:10000]

########
# Plot geomean
########

st.subheader("Throughput versus cost")
fig, ax = plt.subplots(figsize=(8, 6))
for (src_region, dst_region), df_grouped in df.groupby(["problem_src", "problem_dst"]):
    df_grouped.sort_values(by="throughput_achieved_gbits", inplace=True)
    label = "{} to {}".format(src_region, dst_region)
    x = df_grouped["throughput_achieved_gbits"]
    y = df_grouped["cost_total"]
    baseline_throughput = df_grouped["baseline_throughput_achieved_gbits"].min()
    baseline_cost = min(y)
    x = [baseline_throughput] + x.tolist()
    y = [baseline_cost] + y.tolist()
    ax.plot(x, y, label=label, marker="o", linestyle="--")
if st.checkbox("Show legend (absolute)", value=True):
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.6), ncol=3)
ax.set_xlabel("Throughput (Gbps)")
ax.set_ylabel("Cost ($/GB)")
fig.set_facecolor("white")
st.pyplot(fig, bbox_inches="tight")

st.write("Throughput speedup versus cost increase")
fig, ax = plt.subplots(figsize=(8, 6))
for (src_region, dst_region), df_grouped in df.groupby(["problem_src", "problem_dst"]):
    df_grouped["throughput_speedup"] = df_grouped["throughput_achieved_gbits"] / df_grouped["baseline_throughput_achieved_gbits"]
    df_grouped["cost_increase"] = df_grouped["cost_total"] / min(df_grouped["cost_total"])
    df_grouped = df_grouped[df_grouped["throughput_speedup"] > 1]
    df_grouped.sort_values(by="throughput_speedup", inplace=True)

    x = df_grouped["throughput_speedup"]
    y = df_grouped["cost_increase"]
    # add (1, 1)
    x = [1] + list(x)
    y = [1] + list(y)
    label = "{} to {}".format(src_region, dst_region)
    ax.plot(x, y, label=label, alpha=0.8)
if st.checkbox("Show legend (speedup)", value=True):
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.6), ncol=3)
ax.set_xlabel("Throughput speedup (x)")
ax.set_ylabel("Cost increase (x)")
fig.set_facecolor("white")
st.pyplot(fig, bbox_inches="tight")

