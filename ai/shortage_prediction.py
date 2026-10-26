def predict_shortage(quantity):

    if quantity <= 100:
        return "High Risk"

    elif quantity <= 300:
        return "Medium Risk"

    elif quantity <= 500:
        return "Low Risk"

    else:
        return "Healthy Stock"