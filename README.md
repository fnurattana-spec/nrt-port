# nrt-port

หน้าเว็บติดตามพอร์ตกองทุน (EU-US500RMF, UGQGRMF, UOBGRMF-H, TSP3, TSP5)

- `index.html` คือหน้าเว็บ กรอกจำนวนหน่วยและต้นทุนเอง ส่วน NAV อ่านจาก `nav.json`
- `scripts/fetch_nav.py` ดึง NAV ล่าสุดจาก SEC Open API (api.sec.or.th) แล้วเขียน `nav.json`
- `.github/workflows/update-nav.yml` รันสคริปต์ทุกวันทำการ แล้ว commit `nav.json`

## ตั้งค่าครั้งแรก

1. สมัคร API key ฟรีที่ SEC Open Data portal ของ ก.ล.ต. แล้วสมัคร (subscribe) API ข้อมูลกองทุน
   (Fund general info และ Fund daily info)
2. ใน GitHub repo ไปที่ Settings → Secrets and variables → Actions แล้วเพิ่ม secret ชื่อ `SEC_API_KEY`
   (ถ้ามี secondary key ใส่เป็น `SEC_API_KEY_2` ได้)
3. merge เข้า branch หลัก (GitHub รันงานตามเวลาเฉพาะบน branch หลักเท่านั้น)
4. ไปที่ Actions → "อัปเดต NAV" → Run workflow เพื่อสร้าง `nav.json` ครั้งแรก
5. เปิด GitHub Pages: Settings → Pages → Deploy from a branch → branch หลัก / root

ทดลองดึงบนเครื่องตัวเอง: `SEC_API_KEY=xxxx python3 scripts/fetch_nav.py`

ถ้าหา NAV กองไหนไม่เจอ หน้าเว็บจะให้กรอก NAV เองแทน และกรอกทับค่าอัตโนมัติได้ทุกกอง
