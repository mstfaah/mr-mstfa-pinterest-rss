# تغذية Pinterest RSS لمدونة MR.MSTFA

تغذية RSS 2.0 مستقلة لمدونة [mr-mstfa.blogspot.com](https://mr-mstfa.blogspot.com/)، فيها `<media:content>` و`<enclosure>` لكل عنصر حتى يقبلها النشر التلقائي في Pinterest.

بلوجر نفسه لا يضع هذه الوسوم في `/rss.xml`، لذلك تُبنى التغذية هنا يوميًا من التغذية العامة للمدونة **بدون تعديل بلوجر**.

## رابط التغذية (يُلصق في Pinterest بعد التفعيل)

```
https://mstfaah.github.io/mr-mstfa-pinterest-rss/rss.xml
```

روابط العناصر تبقى على `mr-mstfa.blogspot.com` (النطاق المُثبت في Pinterest). ملف التغذية فقط يُستضاف على GitHub Pages.

## التحديث اليومي

GitHub Action باسم **Rebuild Pinterest RSS** يعمل يوميًا الساعة 09:00 بتوقيت قطر (06:00 UTC) وعند التشغيل اليدوي (`workflow_dispatch`). يشغّل `python build_feed.py --max-items 25 -o rss.xml` ويدفع الملف إذا تغيّر.

- البوستات بلا صورة تُستبعد تلقائيًا.
- صور بلوجر المصغّرة (`/s72-c/` و`/s320/` وغيرها) تُحوَّل إلى `/s1600/`.
- عنصر واحد وصورة واحدة لكل بوست.

## الملفات

| الملف | الوظيفة |
|---|---|
| `rss.xml` | التغذية المنشورة |
| `build_feed.py` | المولّد |
| `.github/workflows/rebuild-rss.yml` | التحديث اليومي |

لا تُستخدم هذه التغذية لتغيير المدونة أو موقع `mh3abdo-cell.github.io`. استبدال الرابط داخل إعدادات Pinterest يتم يدويًا بعد التأكد أن الصفحة تعيد HTTP 200 وفيها `media:content`.
