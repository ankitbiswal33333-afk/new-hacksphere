from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import numpy as np
import random

app = Flask(__name__, template_folder='templates')
app.secret_key = "secret_key_lab"
CORS(app)

# --- PHYSICS ENGINE ---
BOLTZMANN_K = 1.380649e-23
ELECTRON_Q = 1.60217663e-19

class DiodePhysics:
    def __init__(self, material, temp_c, zener_v=5.1):
        self.temp_k = float(temp_c) + 273.15
        self.vt = (BOLTZMANN_K * self.temp_k) / ELECTRON_Q
        self.breakdown = -50.0 # Default high breakdown for Si
        self.slope = 10.0
        
        # Material Constants
        if material == 'Si':
            self.Is = 1e-12 * (2 ** ((float(temp_c) - 27) / 10.0))
            self.n = 1.5   
            self.breakdown = -50.0
        elif material == 'Ge':
            self.Is = 1e-6 * (2 ** ((float(temp_c) - 27) / 10.0))
            self.n = 1.0   
            self.breakdown = -20.0
        elif material == 'RedLED':
            self.Is = 1e-18 
            self.n = 2.0   
            self.breakdown = -5.0
        elif material == 'BlueLED':
            self.Is = 1e-24 
            self.n = 3.5   
            self.breakdown = -5.0
        elif material == 'Zener':
            self.Is = 1e-12 * (2 ** ((float(temp_c) - 27) / 10.0))
            self.n = 1.5
            self.breakdown = -float(zener_v)
            self.slope = 0.5

    def compute(self, voltage):
        v = np.asarray(voltage)
        exponent = np.clip(v / (self.n * self.vt), -50, 50)
        i_shockley = self.Is * (np.exp(exponent) - 1)
        i_breakdown = -self.slope * (np.abs(v) - np.abs(self.breakdown))
        current = np.where(v < self.breakdown, i_breakdown, i_shockley)
        if current.ndim == 0: return float(current)
        return current

# --- ROUTES ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/theory')
def theory():
    return render_template('theory.html')

@app.route('/api/measure', methods=['POST'])
def measure():
    data = request.json
    mat = data.get('material', 'Si')
    temp = float(data.get('temp', 27))
    v = float(data.get('voltage', 0))
    
    sim = DiodePhysics(mat, temp)
    i = sim.compute(v)
    
    final_i = i + (i * np.random.uniform(-0.005, 0.005))
    power = v * final_i
    
    limit = 0.5 
    if mat in ['RedLED', 'BlueLED']: limit = 0.05
    status = "OPTIMAL" if abs(power) <= limit else "BURNT (Overheat)"
    
    return jsonify({
        "voltage": v, 
        "current": final_i, 
        "power": power, 
        "status": status,
        "saturation": sim.Is,
        "breakdown": sim.breakdown # SEND BREAKDOWN LIMIT
    })

@app.route('/api/sweep', methods=['POST'])
def sweep():
    data = request.json
    mat = data.get('material', 'Si')
    start = float(data.get('start', -2))
    end = float(data.get('end', 1.5))
    temp = float(data.get('temp', 27))
    
    sim = DiodePhysics(mat, temp)
    
    # 300 Point Sweep for Theory Curve
    voltages = np.linspace(start, end, 300)
    currents = sim.compute(voltages)
    powers = voltages * currents
    
    results = [{"v": round(v, 3), "i": i, "p": p} for v, i, p in zip(voltages, currents.tolist(), powers.tolist())]
    
    # Saddle (Knee)
    threshold = 0.001
    if mat == 'Ge': threshold = 0.0005
    idx = (np.abs(currents - threshold)).argmin()
    saddle_point = {"v": round(voltages[idx], 3), "i": currents[idx]}

    return jsonify({
        "data": results, 
        "saddle": saddle_point,
        "saturation": sim.Is,
        "breakdown": sim.breakdown # CRITICAL FOR GRAPH ZONES
    })

# --- MYSTERY MODE ---
current_mystery = None 
@app.route('/api/start_mystery', methods=['POST'])
def start_mystery():
    global current_mystery
    options = ['Si', 'Ge', 'RedLED', 'BlueLED', 'Zener']
    current_mystery = random.choice(options)
    return jsonify({"status": "Mystery Mode Started"})

@app.route('/api/submit_guess', methods=['POST'])
def submit_guess():
    global current_mystery
    user_guess = request.json.get('guess')
    if user_guess == current_mystery:
        return jsonify({"result": "CORRECT", "actual": current_mystery})
    else:
        return jsonify({"result": "WRONG", "actual": current_mystery})

if __name__ == '__main__':
    app.run(debug=True, port=5000)