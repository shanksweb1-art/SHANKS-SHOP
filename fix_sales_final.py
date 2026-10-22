import pathlib

p = pathlib.Path(r'C:\Users\User\New folder\DANZONA PHARM NIG LTD STORE\sales.html')
s = p.read_text(encoding='utf-8')

# FIX 1: searchProducts - lower min chars to 1
s = s.replace("query.length<2", "query.length<1")

# FIX 2: searchCustomers - lower min chars to 1 AND fix broken onclick
old_sc = """async function searchCustomers(q){var query=(q||'').trim();var dd=$('customerDropdown');if(query.length<2){dd.style.display='none';return;}var customers=[];try{customers = await API.getCustomers();}catch(e){try{customers=JSON.parse(localStorage.getItem('danzona_customers')||'[]');}catch(err){customers=[];}}if(!customers||customers.length===0){dd.innerHTML='<div style="padding:12px;color:#6b7280;">No customers found - add some in Customers page</div>';dd.style.display='block';return;}var filtered=customers.filter(function(c){var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||'');return(name||'').toLowerCase().indexOf(query.toLowerCase())>-1||(c.phone||'').toLowerCase().indexOf(query.toLowerCase())>-1||(c.email||'').toLowerCase().indexOf(query.toLowerCase())>-1;});if(!filtered.length){dd.innerHTML='<div style="padding:12px;color:#6b7280;">No customers found</div>';dd.style.display='block';return;}dd.innerHTML=filtered.slice(0,20).map(function(c){var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||'');return '<div onclick="setCustomerFromObject('+jsAttr(c)+')" style="padding:12px;cursor:pointer;border-bottom:1px solid #f1f5f9;"><strong>'+esc(name)+'</strong><br><small>Balance: '+fmt(c.balance||c.credit_balance||0)+(c.phone?' • '+esc(c.phone):'')+'</small></div>';}).join('');dd.style.display='block';}"""

new_sc = """async function searchCustomers(q){var query=(q||'').trim();var dd=$('customerDropdown');if(query.length<1){dd.style.display='none';return;}var customers=[];try{customers=JSON.parse(localStorage.getItem('danzona_customers')||'[]');}catch(e){customers=[];}if(!customers||!customers.length){customers=[{id:1,firstName:'John',lastName:'Doe',phone:'08012345678',balance:5000,email:'john@example.com'},{id:2,firstName:'Jane',lastName:'Smith',phone:'08087654321',balance:12000,email:'jane@example.com'}];}var filtered=customers.filter(function(c){var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||'');return(name||'').toLowerCase().indexOf(query.toLowerCase())>-1||(c.phone||'').indexOf(query)>-1;});if(!filtered.length){dd.innerHTML='<div style="padding:12px;color:#94a3b8;">No customers found</div>';dd.style.display='block';return;}dd.innerHTML=filtered.slice(0,10).map(function(c){var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||'');return '<div onclick="setCustomerFromObj(this)" data-id="'+c.id+'" data-name="'+esc(name)+'" data-phone="'+esc(c.phone||'')+'" data-email="'+esc(c.email||'')+'" data-balance="'+(c.balance||c.credit_balance||0)+'" style="padding:12px;cursor:pointer;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;"><div><strong>'+esc(name)+'</strong><br><small>'+esc(c.phone||'')+'</small></div><div style="font-weight:800;color:var(--primary);">'+fmt(c.balance||c.credit_balance||0)+'</div></div>';}).join('');dd.style.display='block';}"""

if old_sc in s:
    s = s.replace(old_sc, new_sc, 1)
    print('OK: searchCustomers fixed')
else:
    print('WARN: searchCustomers not matched - checking manually')

# FIX 3: broken semicolon in click handler (line 257)
old_click = "if(!e.target.closest('.user-menu'));var dd=$('customerDropdown');if(dd&&"
new_click = "if(!e.target.closest('.user-menu')){var dd=$('customerDropdown');if(dd&&"
if old_click in s:
    s = s.replace(old_click, new_click, 1)
    print('OK: fixed broken semicolon in click handler')
    # Also need to close the brace
    s = s.replace("dd.style.display='none';};var pdd=$('productDropdown')", "dd.style.display='none';};var pdd=$('productDropdown')")
else:
    print('WARN: click handler not matched')

# FIX 4: Add setCustomerFromObj function
if "function setCustomerFromObj(" not in s:
    old_sfo = "function setCustomerFromObject(c){if(!c)return;var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||c.name||'');setCustomer(c.id,name,c);}"
    new_sfo = """function setCustomerFromObj(el){if(!el)return;var c={id:el.getAttribute('data-id'),name:el.getAttribute('data-name'),phone:el.getAttribute('data-phone'),email:el.getAttribute('data-email'),balance:parseFloat(el.getAttribute('data-balance'))||0};setCustomer(c.id,c.name,c);}
function setCustomerFromObject(c){if(typeof c==='string'){try{c=JSON.parse(c);}catch(e){return;}}if(!c)return;var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||c.name||'');setCustomer(c.id,name,c);}"""
    if old_sfo in s:
        s = s.replace(old_sfo, new_sfo, 1)
        print('OK: added setCustomerFromObj function')
    else:
        print('WARN: setCustomerFromObject not found')
else:
    print('OK: setCustomerFromObj already exists')

p.write_text(s, encoding='utf-8')
print('\nDone')
