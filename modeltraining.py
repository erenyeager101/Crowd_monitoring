import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from datetime import datetime, timedelta
import pymongo

client = pymongo.MongoClient("mongodb+srv://kunalsonne:kunalsonne1847724@cluster0.95mdg.mongodb.net/Auth")
db = client['home']  
collection = db['blogs'] 

data_cursor = collection.find()

data = []
for record in data_cursor:
  
    record.pop('_id', None)
    data.append(record)

df = pd.DataFrame(data)
print(df.head())
print(df.columns) 
df['latitude'] = df['coordinates'].apply(lambda x: x['latitude'] if isinstance(x, dict) else None)
df['longitude'] = df['coordinates'].apply(lambda x: x['longitude'] if isinstance(x, dict) else None)

df = df.drop(columns=['coordinates'])

print(df.head())
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['hour'] = df['timestamp'].dt.hour
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['month'] = df['timestamp'].dt.month
df['minute'] = df['timestamp'].dt.minute
df['latitude'] = df['latitude'] 
df['longitude'] = df['longitude']  
df = df.dropna(subset=['latitude', 'longitude'])
X = df[['latitude', 'longitude', 'hour', 'day_of_week', 'month', 'minute']]
y = df['count']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
print(f'Mean Squared Error: {mean_squared_error(y_test, y_pred)}')
def predict_future_count(location, time_interval_minutes, model):
   
    current_time = datetime.now()
    future_time = current_time + timedelta(minutes=time_interval_minutes)

  
    latitude, longitude = location
    hour = future_time.hour
    day_of_week = future_time.weekday()
    month = future_time.month
    minute = future_time.minute

    future_data = np.array([[latitude, longitude, hour, day_of_week, month, minute]])

    predicted_count = model.predict(future_data)[0]
    return predicted_count

location = (18.5369, 73.8567)
time_interval = 30  
predicted_count = predict_future_count(location, time_interval, model)
print(f'Predicted crowd count in the next {time_interval} minutes: {predicted_count}')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import r2_score, mean_absolute_error

# R-squared (Goodness of fit)
r2 = r2_score(y_test, y_pred)

# Mean Absolute Error (MAE)
mae = mean_absolute_error(y_test, y_pred)

# Plot Actual vs Predicted values
plt.figure(figsize=(10, 6))
plt.scatter(y_test, y_pred, color='blue', alpha=0.6)
plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], color='red', linewidth=2)
plt.xlabel('Actual Values')
plt.ylabel('Predicted Values')
plt.title('Actual vs Predicted Crowd Count')
plt.show()

# Plotting the residuals (difference between predicted and actual)
residuals = y_test - y_pred
plt.figure(figsize=(10, 6))
sns.histplot(residuals, kde=True, color='purple')
plt.title('Residuals Distribution')
plt.xlabel('Residuals')
plt.ylabel('Frequency')
plt.show()

# Printing performance metrics
print(f'R-squared: {r2}')
print(f'Mean Absolute Error: {mae}')
from sklearn.metrics import mean_squared_error, explained_variance_score
import numpy as np

# Mean Squared Error (MSE)
mse = mean_squared_error(y_test, y_pred)

# Root Mean Squared Error (RMSE)
rmse = np.sqrt(mse)

# Explained Variance Score
explained_variance = explained_variance_score(y_test, y_pred)

# Prediction Error (Actual - Predicted)
prediction_error = y_test - y_pred

# Visualizing the prediction error distribution
plt.figure(figsize=(10, 6))
sns.histplot(prediction_error, kde=True, color='orange')
plt.title('Prediction Error Distribution')
plt.xlabel('Prediction Error (Actual - Predicted)')
plt.ylabel('Frequency')
plt.show()

# Visualizing a bar plot of the performance metrics
metrics = {
    'R-squared': r2,
    'Mean Absolute Error': mae,
    'Mean Squared Error': mse,
    'Root Mean Squared Error': rmse,
    'Explained Variance Score': explained_variance
}

plt.figure(figsize=(10, 6))
plt.bar(metrics.keys(), metrics.values(), color='green')
plt.title('Model Performance Metrics')
plt.ylabel('Score')
plt.show()

# Printing all performance metrics
print(f'R-squared: {r2}')
print(f'Mean Absolute Error: {mae}')
print(f'Mean Squared Error: {mse}')
print(f'Root Mean Squared Error: {rmse}')
print(f'Explained Variance Score: {explained_variance}')
