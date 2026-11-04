# Lottery Statistical Analyzer
ติดตั้ง (ฟรี ~10 นาที)
1. สมัคร github.com แล้วสร้าง repository ใหม่ (Public) ชื่ออะไรก็ได้
2. กด "uploading an existing file" แล้วอัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ (รวมโฟลเดอร์ .github และ scripts)
3. Settings → Pages → Source: "Deploy from a branch" → Branch: main / (root) → Save
4. แท็บ Actions → เลือก "update-data" → Run workflow (รันครั้งแรกจะดึงหวยไทยย้อนหลังประมาณ 40 งวด และต่อไปจะรันเองทุกวัน)
5. เปิดเว็บที่ https://<ชื่อผู้ใช้>.github.io/<ชื่อ repo>/

หวยลาว/ฮานอย: เพิ่มผลเองในไฟล์ manual.csv (type,date,variant,number,lower2) เช่น
lao,2026-11-04,main,0731,
hanoi,2026-11-04,normal,4736,86
เลขเก็บเป็นข้อความ เลข 0 นำหน้าไม่หาย และระบบข้ามงวดซ้ำให้เอง
ทดสอบ: python scripts/update.py --selftest
