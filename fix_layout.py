import pathlib

p = pathlib.Path(r'C:\Users\User\New folder\DANZONA PHARM NIG LTD STORE\sales.html')
s = p.read_text(encoding='utf-8')

# Find the exact cart table header and empty state
old_table_header = """<thead><tr><th>Item Name</th><th>Price</th><th>Qty.</th><th>Discount</th><th>Total</th><th></th></tr></thead>"""
new_table_header = """<thead><tr><th>Item Name</th><th>Price</th><th>Qty.</th><th>Discount</th><th>Total</th></tr></thead>"""

if old_table_header in s:
    s = s.replace(old_table_header, new_table_header, 1)
    print('OK: removed extra empty header column')
else:
    print('NOT FOUND: table header')

# Find and replace empty state message
old_empty = """'<div class="empty-state">No items in cart yet</div>'"""
new_empty = """'<div class="empty-state">There are no items in the cart <span style="color:var(--primary);font-weight:700;">[Sales]</span></div>'"""

if old_empty in s:
    s = s.replace(old_empty, new_empty, 1)
    print('OK: updated empty state message')
else:
    print('NOT FOUND: empty state')

# Update the cart panel structure to move customer selector outside/below search properly
# First, ensure customer selector is in the right cart-panel area before totals
old_customer_line = """<div id="cartCustomer" class="cart-customer"><i class="fas fa-user-circle"></i><span id="customerText">Select Customer (optional)</span></div>"""
new_customer_line = """<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><span style="font-size:12px;color:var(--muted);font-weight:700;">Customer</span><button onclick="addQuickCustomer()" style="background:none;border:none;color:var(--primary);cursor:pointer;font-size:18px;padding:4px 8px;" title="Add Customer"><i class="fas fa-user-plus"></i></button></div><input type="text" id="customerSearch" class="search-input" placeholder="Type customer name..." style="min-width:0;width:100%;margin-bottom:10px;" autocomplete="off"><div id="customerDropdown" class="product-dropdown" style="position:relative;top:0;margin-bottom:8px;"></div><div id="cartCustomer"></div>"""

if old_customer_line in s:
    s = s.replace(old_customer_line, new_customer_line, 1)
    print('OK: replaced customer selector with search + add button')
else:
    print('NOT FOUND: customer selector')

# Add keyboard shortcuts footer
old_body_end = """</div>
<div class="toast" id="toast"></div>
</body>
</html>"""

new_body_end = """</div>
      <div style="padding:12px 18px;text-align:center;border-top:1px solid var(--border);background:#fff;margin-top:12px;border-radius:0 0 16px 16px;">
        <a href="#" onclick="toggleShortcuts()" style="font-size:12px;color:var(--primary);font-weight:700;text-decoration:none;"><i class="fas fa-keyboard"></i> Keyboard shortcuts help</a>
      </div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<div class="modal-overlay" id="shortcutsModal">
  <div class="modal" style="max-width:520px;">
    <div class="modal-header"><h3><i class="fas fa-keyboard"></i> Keyboard Shortcuts</h3><button class="modal-close" onclick="POS.closeModal('shortcutsModal')">&times;</button></div>
    <div class="form-row" style="margin-top:8px;">
      <div class="form-group"><label class="required">F1</label><input class="form-control" value="Focus product search" readonly></div>
      <div class="form-group"><label class="required">F2</label><input class="form-control" value="Focus customer search" readonly></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label class="required">F3</label><input class="form-control" value="Focus amount tendered" readonly></div>
      <div class="form-group"><label class="required">F5</label><input class="form-control" value="Toggle product grid" readonly></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label class="required">F8</label><input class="form-control" value="Clear cart" readonly></div>
      <div class="form-group"><label class="required">F9</label><input class="form-control" value="Print receipt" readonly></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label class="required">F12</label><input class="form-control" value="Quick checkout" readonly></div>
    </div>
    <div class="modal-actions"><button class="btn btn-secondary" onclick="POS.closeModal('shortcutsModal')">Close</button></div>
  </div>
</div>
<script>function toggleShortcuts(){POS.openModal('shortcutsModal');}</script>
</body>
</html>"""

if old_body_end in s:
    s = s.replace(old_body_end, new_body_end, 1)
    print('OK: added keyboard shortcuts footer and modal')
else:
    print('NOT FOUND: body end')

p.write_text(s, encoding='utf-8')
print('\nDone')
