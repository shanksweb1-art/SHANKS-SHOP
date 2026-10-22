import pathlib
p=pathlib.Path(r'C:\Users\User\New folder\DANZONA PHARM NIG LTD STORE\sales.html')
s=p.read_text(encoding='utf-8')
checks=[
('closeMenu','function closeMenu()'),
('loadUser','function loadUser()'),
('updateTopClock->liveClock',"$('liveClock')"),
('search min 1','query.length<1'),
('search safe onclick','setCustomerFromObj(this)'),
('setCustomerFromObj def','function setCustomerFromObj('),
]
for n,pat in checks:
    print(n, 'OK' if pat in s else 'MISSING')
