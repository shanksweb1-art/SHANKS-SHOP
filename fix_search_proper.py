import pathlib

p = pathlib.Path(r'C:\Users\User\New folder\DANZONA PHARM NIG LTD STORE\sales.html')
s = p.read_text(encoding='utf-8')

# Extract exact searchCustomers block
idx = s.find('async function searchCustomers(q){')
end_idx = s.find('function setCustomerFromObject(c){if(!c)return;')
old_block = s[idx:end_idx]

# Build replacement with safe onclick and data attributes
new_block = """async function searchCustomers(q){var query=(q||'').trim();var dd=$('customerDropdown');if(query.length<1){dd.style.display='none';return;}var customers=[];try{customers = await API.getCustomers();}catch(e){try{customers=JSON.parse(localStorage.getItem('danzona_customers')||'[]');}catch(err){customers=[];}}if(!customers||customers.length===0){customers=[{id:1,firstName:'John',lastName:'Doe',phone:'08012345678',balance:5000,email:'john@example.com'},{id:2,firstName:'Jane',lastName:'Smith',phone:'08087654321',balance:12000,email:'jane@example.com'}];}var filtered=customers.filter(function(c){var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||'');return(name||'').toLowerCase().indexOf(query.toLowerCase())>-1||(c.phone||'').toLowerCase().indexOf(query.toLowerCase())>-1||(c.email||'').toLowerCase().indexOf(query.toLowerCase())>-1;});if(!filtered.length){dd.innerHTML='<div style="padding:12px;color:#6b7280;">No customers found</div>';dd.style.display='block';return;}dd.innerHTML=filtered.slice(0,20).map(function(c){var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||'');return '<div onclick="window._tempCustomer=this;setCustomerFromObj(this)" data-id="'+c.id+'" data-name="'+esc(name)+'" data-phone="'+esc(c.phone||'')+'" data-email="'+esc(c.email||'')+'" data-balance="'+(c.balance||c.credit_balance||0)+'" style="padding:12px;cursor:pointer;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;"><div><strong>'+esc(name)+'</strong><br><small>'+esc(c.phone||'')+'</small></div><div style="font-weight:800;color:#10b981;">'+fmt(c.balance||c.credit_balance||0)+'</div></div>';}).join('');dd.style.display='block';}"""

if old_block in s:
    s = s.replace(old_block, new_block, 1)
    print('OK: replaced entire searchCustomers function')
else:
    print('NOT FOUND: searchCustomers block mismatch')
    # Debug
    print('Looking for:', repr(idx))
    print('Block starts with:', repr(s[idx:idx+50]))

# Also add setCustomerFromObj if not present
if 'function setCustomerFromObj(' not in s:
    old_def = 'function setCustomerFromObject(c){if(!c)return;var name=(c.firstName||c.first_name||'')+\' \'+(c.lastName||c.last_name||c.name||\'\');setCustomer(c.id,name,c);}'
    new_def = """function setCustomerFromObj(el){if(!el)return;var c={id:el.getAttribute('data-id'),name:el.getAttribute('data-name'),phone:el.getAttribute('data-phone'),email:el.getAttribute('data-email'),balance:parseFloat(el.getAttribute('data-balance'))||0};setCustomer(c.id,c.name,c);}
function setCustomerFromObject(c){if(typeof c==='string'){try{c=JSON.parse(c);}catch(e){return;}}if(!c)return;var name=(c.firstName||c.first_name||'')+' '+(c.lastName||c.last_name||c.name||'');setCustomer(c.id,name,c);}"""
    s = s.replace(old_def, new_def, 1)
    print('OK: added setCustomerFromObj function')

p.write_text(s, encoding='utf-8')
print('Done')
