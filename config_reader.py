import configparser
import os

class Config:
    def __init__(self, config_path='config.ini'):
        self.config = configparser.ConfigParser()
        if os.path.exists(config_path):
            try:
                # Пробуем разные кодировки
                encodings = ['utf-8', 'utf-8-sig', 'cp1251']
                for encoding in encodings:
                    try:
                        with open(config_path, 'r', encoding=encoding) as f:
                            self.config.read_file(f)
                        break
                    except UnicodeDecodeError:
                        continue
            except Exception as e:
                print(f"Ошибка при чтении конфига: {e}")
        
    def get_video_options(self):
        if 'option_video' not in self.config:
            return {}
        
        options = self.config['option_video']
        return {
            'contrast': float(options.get('contrast', 1.02)),
            'saturation': float(options.get('saturation', 1.02)),
            'gamma': float(options.get('gamma', 1.0)),
            'gamma_r': float(options.get('gamma_r', 1.0)),
            'gamma_g': float(options.get('gamma_g', 1.0)),
            'gamma_b': float(options.get('gamma_b', 1.0)),
            'gamma_weight': float(options.get('gamma_weight', 0.4)),
            'vibrance': float(options.get('vibrance', 0.05)),
            'eq': float(options.get('eq', 0.07)),
            'fps': int(options.get('fps', 24)),
            'random_config': options.get('random_config', 'False').lower() == 'true'
        }
