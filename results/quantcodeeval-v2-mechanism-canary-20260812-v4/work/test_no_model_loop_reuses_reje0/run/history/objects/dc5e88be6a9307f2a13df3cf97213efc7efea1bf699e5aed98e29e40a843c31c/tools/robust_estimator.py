def robust_estimator(values):
    values = [float(value) for value in values]
    return {'estimate': sum(values) / len(values)}
