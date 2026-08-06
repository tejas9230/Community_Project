from ai.classifier import predict_complaint

complaint = input("Enter Complaint: ")

result = predict_complaint(complaint)

print(result)