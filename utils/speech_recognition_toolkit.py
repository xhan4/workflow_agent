import os
import json
import threading
import audioop
import pyaudio
import speech_recognition as sr
from vosk import Model, KaldiRecognizer
from dotenv import load_dotenv
from pynput import keyboard

load_dotenv()

class SpeechRecognitionToolkit:
    def __init__(self, trigger_key='F2'):
        self.trigger_key = trigger_key
        self.is_recording = False
        self.start_event = threading.Event()  # 使用 Event 控制录音开始
        self.model_path = os.path.join("models", "vosk-model-small-cn-0.22")
        self.sample_rate = 16000
        
        # 加载模型
        try:
            self.model = self._load_model()
        except Exception as e:
            print(f"加载模型失败: {e}")
            raise
        
        # 键盘监听线程
        self.listener = None
        self.keyboard_thread = threading.Thread(target=self._keyboard_listener)
        self.keyboard_thread.daemon = True
        self.keyboard_thread.start()

    def _keyboard_listener(self):
        """监听按键按下和松开事件"""
        def on_press(key):
            try:
                key_name = key.char.lower()
            except AttributeError:
                key_name = key.name.lower()
            
            if key_name == self.trigger_key.lower() and not self.is_recording:
                print(f"\n检测到 [{self.trigger_key.upper()}] 按下，准备开始录音...")
                self.start_event.set()  # 设置 Event 信号

        def on_release(key):
            try:
                key_name = key.char.lower()
            except AttributeError:
                key_name = key.name.lower()
            
            if key_name == self.trigger_key.lower():
                print(f"\n检测到 [{self.trigger_key.upper()}] 松开，停止录音...")
                self.is_recording = False

        # 启动键盘监听器
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            self.listener = listener
            listener.join()

    def _load_model(self):
        """加载语音识别模型"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径错误: {self.model_path}")
        return Model(self.model_path)

    def _get_volume_level(self, chunk, sample_width):
        """计算并返回音量可视化字符串"""
        rms = audioop.rms(chunk, sample_width)
        level = min(int(rms / 2000), 10)  # 根据实际情况调整除数
        return "█" * level + " " * (10 - level)

    def recognize_speech(self):
        """执行语音识别（需要外部触发）"""
        recognizer = sr.Recognizer()
        vosk_recognizer = KaldiRecognizer(self.model, self.sample_rate)
        
        try:
            with sr.Microphone(sample_rate=self.sample_rate) as source:
                recognizer.adjust_for_ambient_noise(source)
                
                audio_data = []
                stream = source.stream
                sample_width = pyaudio.get_sample_size(source.format)

                # 等待录音开始
                print("\n等待语音输入...（长按 {} 开始录音）".format(self.trigger_key.upper()))
                self.start_event.wait()  # 等待 Event 信号
                self.start_event.clear()  # 清除信号
                self.is_recording = True
                print("开始录音...")

                while self.is_recording:
                    try:
                        # 读取音频数据
                        chunk = stream.read(1024)
                        audio_data.append(chunk)
                        
                        # 声音可视化（每0.1秒更新）
                        if len(audio_data) % 4 == 0:  # 1024*4≈0.1秒
                            volume = self._get_volume_level(chunk, sample_width)
                            print(f"\r音量: [{volume}]", end="", flush=True)
                    except (IOError, OSError) as e:
                        # 捕获缓冲区溢出异常
                        print(f"\n警告: 音频缓冲区溢出，继续录音...")
                        continue

                # 生成音频对象
                audio = sr.AudioData(
                    b''.join(audio_data),
                    sample_rate=self.sample_rate,
                    sample_width=sample_width
                )

                # 获取识别结果
                if vosk_recognizer.AcceptWaveform(audio.get_raw_data()):
                    result = json.loads(vosk_recognizer.Result())
                    text = result.get("text", "").strip()
                else:
                    partial = json.loads(vosk_recognizer.PartialResult())
                    text = partial.get("partial", "").strip()
                
                return text.replace(" ", "")

        except Exception as e:
            print(f"发生错误: {str(e)}")
        finally:
            self.is_recording = False
            print()  # 确保换行
            
        return ""
