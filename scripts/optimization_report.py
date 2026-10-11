"""Build an offline side-by-side screenshot index from measured browser output."""
import json,html
from pathlib import Path
from PIL import Image,ImageChops
for folder in ('final-visual','page-comments-visual'):
    root=Path('reports/optimization')/folder
    data=json.loads((root/'results.json').read_text())
    assert all(row['status']==200 for row in data['pages'])
    assert all(not row['errors'] for row in data['pages'] if row['label']=='after')
    pairs=[];cards=[]
    for before in sorted(root.glob('*-before-*.png')):
        after=root/before.name.replace('-before-','-after-')
        assert after.exists(),after
        with Image.open(before) as old,Image.open(after) as new:
            item={'before':before.name,'after':after.name,'before_size':list(old.size),'after_size':list(new.size)}
            if old.size==new.size:
                delta=ImageChops.difference(old.convert('RGB'),new.convert('RGB'))
                changed=sum(px!=(0,0,0) for px in delta.get_flattened_data())
                item['different_pixels']=changed;item['fraction_changed']=changed/(old.width*old.height)
        pairs.append(item)
        cards.append(f'<h2>{html.escape(before.name.replace("-before-"," "))}</h2><div class="pair"><a href="{before.name}"><span>修改前</span><img loading="lazy" src="{before.name}"></a><a href="{after.name}"><span>修改后</span><img loading="lazy" src="{after.name}"></a></div>')
    (root/'comparison.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2)+'\n')
    (root/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>第二阶段视觉证据</title><style>body{font:16px system-ui;margin:24px;background:#f5f5f5}h2{font-size:18px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.pair a{background:white;padding:12px}.pair span{display:block;margin-bottom:12px}.pair img{width:100%;height:auto}</style><h1>修改前后视觉对比</h1><p>合成测试数据；点击图片查看完整分辨率。主题保持，文字/评论/图标为有记录的修复差异。GIF、字体fallback和hover可能产生额外光栅差异；不代表生产像素验收。</p>'+''.join(cards)+'</html>')
    print(folder,len(data['pages']),'browser pages',len(pairs),'screenshot pairs')
