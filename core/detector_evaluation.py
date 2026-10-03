"""Local annotation-assistance evaluation; center matching is not benchmark mAP."""
import numpy as np
from scipy.optimize import linear_sum_assignment

PROFILES={'precise':.55,'balanced':.3,'recall':.15}

def score_predictions(predictions, truth, distance_limit=2.0):
    rows={}
    for label in sorted({box.label for box in predictions+truth}):
        pred=[box for box in predictions if box.label==label]
        gt=[box for box in truth if box.label==label]
        matches=[]
        if pred and gt:
            distance=np.linalg.norm(np.array([box.center for box in pred])[:,None,:]-np.array([box.center for box in gt])[None,:,:],axis=2)
            # A large penalty prioritizes number of valid matches before distance.
            costs=np.where(distance<=distance_limit,distance,1e6)
            a,b=linear_sum_assignment(costs)
            matches=[(i,j,float(distance[i,j])) for i,j in zip(a,b) if distance[i,j]<=distance_limit]
        rows[label]={'tp':len(matches),'fp':len(pred)-len(matches),'fn':len(gt)-len(matches),
                     'center_error_sum':sum(d for _,_,d in matches),
                     'size_error_sum':sum(float(np.mean(np.abs(np.array(pred[i].size)-gt[j].size))) for i,j,_ in matches)}
    return aggregate_scores([{'by_label':rows}])

def aggregate_scores(scores):
    rows={}
    for score in scores:
        for label,row in score['by_label'].items():
            target=rows.setdefault(label,{key:0 for key in ['tp','fp','fn','center_error_sum','size_error_sum']})
            for key in target:target[key]+=row[key]
    def metrics(row):
        tp,fp,fn=row['tp'],row['fp'],row['fn']
        return {**row,'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/(tp+fn) if tp+fn else 0,
                'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
                'center_error_m':row['center_error_sum']/tp if tp else None,
                'size_error_m':row['size_error_sum']/tp if tp else None}
    total={key:sum(row[key] for row in rows.values()) for key in ['tp','fp','fn','center_error_sum','size_error_sum']}
    return {**metrics(total),'by_label':{label:metrics(row) for label,row in rows.items()}}
