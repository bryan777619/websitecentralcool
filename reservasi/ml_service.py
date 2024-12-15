import os
import logging
import joblib
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
from io import BytesIO
import base64

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ACServicePreprocessor:
    def __init__(self):
        self.symptom_features = [
            'masalah_ac_kurang_dingin',
            'masalah_ac_mengeluarkan_bau',
            'masalah_bunyi_menggeram_dari_kap_mobil',
            'masalah_freon_cepat_habis',
            'masalah_genangan_air_didalam_kabin',
            'masalah_mesin_mobil_overheat',
            'masalah_muncul_tetesan_oli_freon',
            'masalah_suhu_ac_cepat_berubah',
            'masalah_udara_ac_kecil'
        ]
        
        self.car_type_features = [
            'jenis_mobil_hatchback',
            'jenis_mobil_mpv',
            'jenis_mobil_sedan',
            'jenis_mobil_suv'
        ]
        
        self.car_brand_features = [
            'merek_mobil_daihatsu',
            'merek_mobil_honda',
            'merek_mobil_isuzu',
            'merek_mobil_mazda',
            'merek_mobil_mitsubishi',
            'merek_mobil_nissan',
            'merek_mobil_suzuki',
            'merek_mobil_toyota'
        ]
        
        self.service_types = [
            'pergantian_ekspansi',
            'pergantian_kondensor',
            'pergantian_evaporator',
            'pergantian_filter_kabin',
            'pergantian_kompresor',
            'pergantian_magnet_clutch',
            'pergantian_motor_blower',
            'pergantian_motor_fan',
            'pergantian_selang_ac'
        ]

        self.symptom_mapping = {
            'AC Kurang Dingin': 'masalah_ac_kurang_dingin',
            'AC Mengeluarkan Bau': 'masalah_ac_mengeluarkan_bau',
            'Bunyi Menggeram dari Kap Mobil': 'masalah_bunyi_menggeram_dari_kap_mobil',
            'Freon Cepat Habis': 'masalah_freon_cepat_habis',
            'Genangan Air DiDalam Kabin': 'masalah_genangan_air_didalam_kabin',
            'Mesin Mobil Overheat': 'masalah_mesin_mobil_overheat',
            'Muncul Tetesan Oli Freon': 'masalah_muncul_tetesan_oli_freon',
            'Suhu AC Cepat Berubah': 'masalah_suhu_ac_cepat_berubah',
            'Udara AC Kecil': 'masalah_udara_ac_kecil'
        }
        
        self.service_descriptions = {
            'pergantian_ekspansi': 'Penggantian ekspansi untuk mengoptimalkan aliran refrigeran',
            'pergantian_kondensor': 'Penggantian kondensor untuk meningkatkan efisiensi pendinginan',
            'pergantian_evaporator': 'Penggantian evaporator untuk memperbaiki proses pendinginan udara',
            'pergantian_filter_kabin': 'Penggantian filter untuk membersihkan udara dan menghilangkan bau',
            'pergantian_kompresor': 'Penggantian kompresor AC yang sudah tidak efisien',
            'pergantian_magnet_clutch': 'Penggantian magnet clutch yang aus atau rusak',
            'pergantian_motor_blower': 'Penggantian motor blower untuk memperbaiki hembusan udara',
            'pergantian_motor_fan': 'Penggantian motor fan kondensor yang bermasalah',
            'pergantian_selang_ac': 'Penggantian selang AC yang bocor atau rusak'
        }

    def create_feature_vector(self, symptom, car_type, car_brand):
        """Create a feature vector for prediction with improved error handling"""
        try:
            # Initialize feature vector
            feature_vector = pd.DataFrame(0, 
                index=[0], 
                columns=self.symptom_features + self.car_type_features + self.car_brand_features
            )
            
            # Process symptom
            symptom_feature = None
            for key, value in self.symptom_mapping.items():
                if key.lower() in symptom.lower():
                    symptom_feature = value
                    break
            
            if not symptom_feature:
                raise ValueError(f"Gejala tidak valid: {symptom}")
            
            # Set features
            feature_vector[symptom_feature] = 1
            feature_vector[f'jenis_mobil_{car_type.lower()}'] = 1
            feature_vector[f'merek_mobil_{car_brand.lower()}'] = 1
            
            return feature_vector
            
        except Exception as e:
            logger.error(f"Error creating feature vector: {str(e)}")
            raise

    def load_and_preprocess_data(self, data_path):
        """Load and preprocess the training data with validation"""
        try:
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"File dataset tidak ditemukan: {data_path}")
            
            df = pd.read_csv(data_path)
            
            # Validate columns
            all_features = (
                self.symptom_features + 
                self.car_type_features + 
                self.car_brand_features
            )
            
            service_columns = [f'jenis_layanan_{s}' for s in self.service_types]
            
            missing_cols = [col for col in all_features + service_columns if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Kolom yang diperlukan tidak ditemukan: {missing_cols}")
            
            # Prepare features and target
            X = df[all_features]
            y = df[service_columns].idxmax(axis=1).apply(lambda x: x.replace('jenis_layanan_', ''))
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preprocessing data: {str(e)}")
            raise

class ACServiceRecommender:
    def __init__(self, data_path=None, model_path=None):
        self.preprocessor = ACServicePreprocessor()
        
        # Initialize models with optimized parameters
        self.dt_model = DecisionTreeClassifier(
            random_state=235,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced'
        )
        
        self.rf_model = RandomForestClassifier(
            n_estimators=200,
            random_state=235,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced',
            n_jobs=-1
        )
        
        self.model_performances = {}
        self.best_model = None
        self.best_model_name = None
        self.confidence_score = None
        self.confusion_matrices = {}
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        elif data_path:
            self.load_and_train_models(data_path)
        else:
            raise ValueError("Data path atau model path harus disediakan")

    def generate_confusion_matrix_plot(self, cm, labels, title):
        """Generate a confusion matrix plot and return as base64 string"""
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                   xticklabels=labels, yticklabels=labels)
        plt.title(title)
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def load_and_train_models(self, data_path):
        """Train both models and compare performance"""
        try:
            X, y = self.preprocessor.load_and_preprocess_data(data_path)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=155, stratify=y
            )
            
            # Train and evaluate models
            models = {
                'Decision Tree': self.dt_model,
                'Random Forest': self.rf_model
            }
            
            best_score = 0
            class_labels = sorted(list(set(y)))

            for name, model in models.items():
                # Train
                model.fit(X_train, y_train)

                y_pred = model.predict(X_test)

                cm = confusion_matrix(y_test, y_pred)
                cm_plot = self.generate_confusion_matrix_plot(
                    cm, class_labels, f'Confusion Matrix - {name}'
                )
                
                # Evaluate
                cv_scores = cross_val_score(model, X, y, cv=5)
                train_score = model.score(X_train, y_train)
                test_score = model.score(X_test, y_test)

                class_report = classification_report(y_test, y_pred, output_dict=True)
                
                # Store metrics
                self.model_performances[name] = {
                    'cv_score': np.mean(cv_scores),
                    'cv_std': np.std(cv_scores),
                    'train_score': train_score,
                    'test_score': test_score,
                    'confusion_matrix': cm.tolist(),
                    'confusion_matrix_plot': cm_plot,
                    'classification_report': class_report
                }
                
                # Update best model
                if test_score > best_score:
                    best_score = test_score
                    self.best_model = model
                    self.best_model_name = name
                    self.confidence_score = test_score
            
            logger.info("Model training and evaluation completed successfully")
            self.save_model(data_path.replace('.csv', '_model.joblib'))
            
        except Exception as e:
            logger.error(f"Error in model training: {str(e)}")
            raise

    def predict(self, symptom, car_type, car_brand):
        """Generate service recommendation"""
        try:
            if not self.best_model:
                raise ValueError("Model belum dilatih atau dimuat")
                
            features = self.preprocessor.create_feature_vector(symptom, car_type, car_brand)
            prediction = self.best_model.predict(features)[0]
            probabilities = self.best_model.predict_proba(features)[0]
            confidence = np.max(probabilities)
            
            return prediction, confidence, self.model_performances
            
        except Exception as e:
            logger.error(f"Error in prediction: {str(e)}")
            raise

    def get_service_description(self, service):
        """Get service description with separated disclaimer"""
        try:
            # Get base description without disclaimer
            description = self.preprocessor.service_descriptions.get(
                service,
                "Silakan konsultasikan dengan mekanik kami untuk informasi lebih lanjut."
            )
            
            return description
            
        except Exception as e:
            logger.error(f"Error getting service description: {str(e)}")
            raise

    def save_model(self, path):
        """Save model with all necessary data"""
        try:
            model_data = {
                'model': self.best_model,
                'name': self.best_model_name,
                'score': self.confidence_score,
                'performances': self.model_performances
            }
            
            joblib.dump(model_data, path)
            logger.info(f"Model saved successfully: {path}")
            
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            raise

    def load_model(self, path):
        """Load model with improved error handling"""
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Model file not found: {path}")
                
            model_data = joblib.load(path)
            
            # Validate model data
            required_keys = ['model', 'name', 'score', 'performances']
            missing_keys = [key for key in required_keys if key not in model_data]
            
            if missing_keys:
                raise ValueError(f"Missing data in model file: {missing_keys}")
                
            self.best_model = model_data['model']
            self.best_model_name = model_data['name']
            self.confidence_score = model_data['score']
            self.model_performances = model_data['performances']
            
            logger.info(f"Model loaded successfully: {self.best_model_name}")
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise

# Initialize paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'model')
DATA_DIR = os.path.join(BASE_DIR, 'data')

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

DATA_PATH = os.path.join(DATA_DIR, 'dataset_ac_service_history.csv')
MODEL_PATH = os.path.join(MODEL_DIR, 'ac_service_model.joblib')

# Initialize recommender
try:
    if os.path.exists(DATA_PATH):
        recommender = ACServiceRecommender(data_path=DATA_PATH)
    elif os.path.exists(MODEL_PATH):
        recommender = ACServiceRecommender(model_path=MODEL_PATH)
    else:
        raise FileNotFoundError(
            "Dataset atau model tidak ditemukan. "
            "Pastikan file dataset tersedia di direktori data."
        )
except Exception as e:
    logger.error(f"Failed to initialize recommender: {str(e)}")
    raise