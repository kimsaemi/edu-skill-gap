import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

df_rep = pd.read_csv('data/hr/output/recommendation/cluster_representative_courses.csv')
for c in range(10):
    c_df = df_rep[df_rep['cluster_id'] == c]
    print(f"\n=== Cluster {c} ===")
    for _, r in c_df.iterrows():
        print(f"  [{r['rank']}] ({r['provider']}) {r['title']} | sim: {r['similarity_to_centroid']} | {r['text_richness_status']}")
