from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta
import pymongo

app = Flask(__name__)
CORS(app)  

client = pymongo.MongoClient("mongodb+srv://kunalsonne:kunalsonne1847724@cluster0.95mdg.mongodb.net/Auth")
db = client['home']
collection = db['blogs']

data_cursor = collection.find()
data = []

for record in data_cursor:
    record.pop('_id', None)  
    data.append(record)

df = pd.DataFrame(data)

df['latitude'] = df['coordinates'].apply(lambda x: x['latitude'] if isinstance(x, dict) else None)
df['longitude'] = df['coordinates'].apply(lambda x: x['longitude'] if isinstance(x, dict) else None)
df = df.drop(columns=['coordinates'])
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['hour'] = df['timestamp'].dt.hour
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['month'] = df['timestamp'].dt.month
df['minute'] = df['timestamp'].dt.minute
df = df.dropna(subset=['latitude', 'longitude'])

X = df[['latitude', 'longitude', 'hour', 'day_of_week', 'month', 'minute']]
y = df['count']

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X, y)

def predict_future_count(latitude, longitude, time_interval_minutes):
    current_time = datetime.now()
    future_time = current_time + timedelta(minutes=time_interval_minutes)

    hour = future_time.hour
    day_of_week = future_time.weekday()
    month = future_time.month
    minute = future_time.minute

    future_data = np.array([[latitude, longitude, hour, day_of_week, month, minute]])

    predicted_count = model.predict(future_data)[0]
    return predicted_count

@app.route('/past_trend', methods=['POST'])
def past_trend():
    try:
        data = request.get_json()
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        time_interval = int(data['time_interval'])  
        
        location_data = df[(df['latitude'] == latitude) & (df['longitude'] == longitude)]

        if location_data.empty:
            return jsonify({'error': 'No data available for this location'}), 400

        trend_data = []
        current_time = datetime.now()
        
        for i in range(0, 48):  
            future_time = current_time - timedelta(minutes=i * time_interval)
            future_hour = future_time.hour
            future_day_of_week = future_time.weekday()
            future_month = future_time.month
            future_minute = future_time.minute

            future_data = np.array([[latitude, longitude, future_hour, future_day_of_week, future_month, future_minute]])

            predicted_count = model.predict(future_data)[0]
            trend_data.append({
                'timestamp': future_time.strftime('%Y-%m-%d %H:%M:%S'),
                'predicted_count': predicted_count
            })

        return jsonify({'trend_data': trend_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        time_interval = int(data['time_interval'])

        
        predicted_count = predict_future_count(latitude, longitude, time_interval)

        
        return jsonify({'predicted_count': predicted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
