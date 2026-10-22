import pathlib
p=pathlib.Path(r'C:\Users\User\New folder\DANZONA PHARM NIG LTD STORE\sales.html')
s=p.read_text(encoding='utf-8')
idx=s.find('id="productSearch"')
print(s[idx:idx+400])
