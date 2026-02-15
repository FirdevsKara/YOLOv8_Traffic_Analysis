import cv2
import numpy as np
import os
from ultralytics import YOLO

def setup_environment():
    """YOLO modelini yükler."""
    return YOLO('yolov8n.pt')

def process_traffic_video(input_video, output_video):
    model = setup_environment()
    cap = cv2.VideoCapture(input_video)
    
    if not cap.isOpened():
        print(f"HATA: {input_video} bulunamadı!")
        return

    # Video Özelliklerini Al
    w, h, fps = (int(cap.get(x)) for x in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS))
    video_writer = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

    # Ayarlar ve Değişkenler
    hiz_siniri = 80
    piksel_metre_orani = 15
    onceki_konumlar = {}
    sayilan_idler = set()
    cizgi_y = h // 2 
    pts = np.array([[int(w*0.65), h], [int(w*0.8), h*0.6], [w, h*0.6], [w, h]], np.int32)


    # Takip (Tracking) Başlat
    results = model.track(source=input_video, persist=True, stream=True, conf=0.4, verbose=False)

    for r in results:
        img = r.orig_img.copy() # Temiz kareyi al
        
        # Yasak Bölge ve Çizgi Çizimi
        overlay = img.copy()
        cv2.fillPoly(overlay, [pts], (0, 0, 255))
        img = cv2.addWeighted(overlay, 0.2, img, 0.8, 0)
        cv2.line(img, (0, cizgi_y), (w, cizgi_y), (255, 255, 255), 2)

        if r.boxes.id is not None:
            boxes = r.boxes.xyxy.int().tolist()
            ids = r.boxes.id.int().tolist()
            clss = r.boxes.cls.int().tolist()

            for box, id, cls in zip(boxes, ids, clss):
                if cls != 2: continue # Sadece arabaları (car) işle

                x1, y1, x2, y2 = box
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                y_alt = y2

                # 1. Hız Hesaplama
                # Hız Hesaplama Mantığı:
                # 1. Mesafe: İki kare arasında aracın kaç piksel gittiğini bul (Öklid mesafesi).
                # 2. Hız (m/s): (Piksel Mesafe * FPS) / Oran -> Saniyedeki metre cinsinden hızı verir.
               # 3. Birim Dönüşümü: m/s değerini 3.6 ile çarparak km/h (kilometre/saat) değerine çevir.
                hiz = 0
                if id in onceki_konumlar:
                    eski_cx, eski_cy = onceki_konumlar[id]
                    mesafe = np.sqrt((cx - eski_cx)**2 + (cy - eski_cy)**2)
                    hiz = int((mesafe * fps * 3.6) / piksel_metre_orani)
                onceki_konumlar[id] = (cx, cy)

                # 2. Sayma ve İhlal Kontrolü
                if y_alt > cizgi_y and id not in sayilan_idler:
                    sayilan_idler.add(id)

                is_in_roi = cv2.pointPolygonTest(pts, (cx, y_alt), False) >= 0
                
                # 3. Ekrana Çizdirme
                renk = (0, 0, 255) if (hiz > hiz_siniri or is_in_roi) else (0, 255, 0)
                cv2.rectangle(img, (x1, y1), (x2, y2), renk, 2)
                etiket = f"ID:{id} {hiz} km/h"
                if is_in_roi: etiket += " - IHLAL!"
                cv2.putText(img, etiket, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        cv2.putText(img, f"Toplam Gecen: {len(sayilan_idler)}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 3)
        video_writer.write(img)

    video_writer.release()
    cap.release()
    print("İşlem bitti!")

if __name__ == "__main__":
    # Colab'da çalıştırırken yolları kontrol et!
    process_traffic_video('trafik_videosu.mp4', 'analiz_sonucu.mp4')