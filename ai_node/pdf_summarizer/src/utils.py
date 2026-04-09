"""
Utility functions for PDF Summarizer
Includes: logging, retry mechanism, GPU detection
"""
import logging
import os
from functools import wraps
from time import sleep
from typing import Callable, Any
# تم حذف import ollama من هنا

# Setup logging
def setup_logging(log_file="pdf_summarizer.log", level=logging.INFO):
    """إعداد نظام logging"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_path = os.path.join(log_dir, log_file)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

def retry(max_attempts=3, delay=2, backoff=2, exceptions=(Exception,)):
    """
    Decorator لإعادة المحاولة عند الفشل
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"Attempt {attempt}/{max_attempts} for {func.__name__}")
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            
            raise last_exception
        return wrapper
    return decorator

def check_gpu_availability():
    """التحقق من توفر GPU"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
            logger.info(f"✅ GPU detected: {gpu_name} (Count: {gpu_count})")
            return True, gpu_count, gpu_name
        else:
            logger.info("ℹ️  No GPU detected, using CPU")
            return False, 0, None
    except ImportError:
        logger.info("ℹ️  PyTorch not installed, GPU check skipped (Ollama will handle GPU)")
        return False, 0, None
    except Exception as e:
        logger.warning(f"⚠️  Error checking GPU: {str(e)}")
        return False, 0, None

def get_ollama_gpu_layers():
    """الحصول على عدد طبقات GPU الموصى بها"""
    has_gpu, gpu_count, gpu_name = check_gpu_availability()
    if has_gpu:
        return -1
    return 0

def get_model_config(model_name, temperature, max_tokens, use_gpu=True):
    """
    الحصول على إعدادات النموذج مع دعم GPU
    """
    config = {
        "model": model_name,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }
    
    if use_gpu:
        gpu_layers = get_ollama_gpu_layers()
        if gpu_layers != 0:
            config["options"]["num_gpu"] = gpu_layers
            logger.info(f"🚀 GPU acceleration enabled: {gpu_layers} layers")
        else:
            logger.info("💻 Using CPU mode")
    
    return config