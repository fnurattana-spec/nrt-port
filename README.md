# nrt-port

หน้าเว็บติดตามพอร์ตกองทุน (EU-US500RMF, UGQGRMF, UOBGRMF-H, TSP3, TSP5)

- `index.html` คือหน้าเว็บ กรอกจำนวนหน่วยและต้นทุนเอง ส่วน NAV อ่านจาก `nav.json`
- `scripts/fetch_nav.py` ดึง NAV ล่าสุดแล้วเขียน `nav.json`
- `.github/workflows/update-nav.yml` รันสคริปต์ทุกวันทำการ แล้ว commit `nav.json`

## แหล่ง NAV

- ค่าเริ่มต้นดึงจาก **Finnomena** ไม่ต้องสมัครหรือใช้ key แต่เป็น API ที่ไม่ได้เปิดอย่างเป็นทางการ วันหนึ่งอาจเปลี่ยนหรือใช้ไม่ได้
- ถ้าเพิ่ม secret `SEC_API_KEY` (key จาก SEC Open Data portal ของ ก.ล.ต.) ไว้ จะดึงจาก ก.ล.ต. ก่อน กองไหนดึงไม่ได้จะไปลอง Finnomena แทน

## ตั้งค่าครั้งแรก

1. ไปที่ Actions → "อัปเดต NAV" → Run workflow เพื่อสร้าง `nav.json` ครั้งแรก
2. เปิด GitHub Pages: Settings → Pages → Deploy from a branch → `main` / root

ทดลองดึงบนเครื่องตัวเอง: `python3 scripts/fetch_nav.py`

ถ้าหา NAV กองไหนไม่เจอ หน้าเว็บจะให้กรอก NAV เองแทน และกรอกทับค่าอัตโนมัติได้ทุกกอง
