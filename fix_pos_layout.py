import pathlib

p = pathlib.Path(r'C:\Users\User\New folder\DANZONA PHARM NIG LTD STORE\sales.html')
s = p.read_text(encoding='utf-8')

# Replace entire pos-wrap section with clean 3-column layout
old_start = '    <div class="pos-wrap">'
old_end = '    <div style="padding:10px 18px;text-align:center;border-top:1px solid var(--border);background:transparent;margin-top:8px;">'

start_idx = s.find(old_start)
end_idx = s.find(old_end)

if start_idx != -1 and end_idx != -1:
    new_layout = """    <div class="pos-wrap">
      <div class="products-panel">
        <div class="products-header">
          <input type="text" id="productSearch" placeholder="Enter item name or scan barcode" autocomplete="off" style="flex:1;padding:14px 18px;border:2px solid var(--border);border-radius:12px;font-size:15px;outline:none;">
          <div id="productDropdown" class="product-dropdown"></div>
          <button class="btn btn-primary" onclick="checkout()" style="white-space:nowrap;padding:14px 28px;font-size:14px;border-radius:10px;font-weight:800;"><i class="fas fa-check-circle"></i> Sale</button>
          <button class="btn btn-info" onclick="toggleGrid()" style="white-space:nowrap;padding:14px 28px;font-size:14px;border-radius:10px;font-weight:800;background:#2563eb;color:#fff;border:0;"><i class="fas fa-th-large"></i> Show Grid</button>
        </div>
        <div class="products-grid hidden" id="productsGrid"></div>
      </div>

      <div class="cart-panel" style="background:#fff;border:1px solid var(--border);border-radius:16px;box-shadow:0 4px 6px -1px rgba(0,0,0,.05);display:flex;flex-direction:column;min-height:0;overflow:hidden;">
        <div style="padding:16px 18px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
          <h3 style="margin:0;font-size:16px;font-weight:800;color:var(--text);"><i class="fas fa-cart-shopping"></i> Cart</h3>
          <span id="cartCount" style="font-size:12px;color:var(--muted);font-weight:700;">0 items</span>
        </div>
        <div style="flex:1;overflow-y:auto;min-height:0;">
          <table class="cart-table" style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="background:#f8fafc;border-bottom:1px solid var(--border);">
                <th style="padding:12px 14px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:800;color:#475569;">Item Name</th>
                <th style="padding:12px 14px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:800;color:#475569;">Price</th>
                <th style="padding:12px 14px;text-align:center;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:800;color:#475569;">Qty.</th>
                <th style="padding:12px 14px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:800;color:#475569;">Discount</th>
                <th style="padding:12px 14px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:800;color:#475569;">Total</th>
              </tr>
            </thead>
            <tbody id="cartItems">
              <tr><td colspan="5" class="empty-state" style="padding:40px 16px;">There are no items in the cart <span style="color:var(--primary);font-weight:700;">[Sales]</span></td></tr>
            </tbody>
          </table>
        </div>
        <div style="padding:14px 18px;border-top:1px solid var(--border);background:#f8fafc;">
          <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;"><span>Sub Total</span><span id="subTotal" style="font-weight:700;">₦0.00</span></div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;"><span>Discount</span><span id="discountTotal" style="font-weight:700;">₦0.00</span></div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;font-size:16px;font-weight:900;color:var(--text);border-top:1px solid var(--border);margin-top:4px;"><span>Total</span><span id="totalAmount">₦0.00</span></div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:14px;font-weight:800;color:var(--primary);"><span>Amount Due</span><span id="amountDue">₦0.00</span></div>
        </div>
      </div>

      <div class="customer-panel" style="background:#fff;border:1px solid var(--border);border-radius:16px;box-shadow:0 4px 6px -1px rgba(0,0,0,.05);display:flex;flex-direction:column;min-height:0;">
        <div style="padding:14px 18px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:12px;color:var(--muted);font-weight:700;">CUSTOMER</span>
          <button onclick="addQuickCustomer()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;padding:4px 8px;letter-spacing:2px;" title="More options"><i class="fas fa-ellipsis"></i></button>
        </div>
        <div style="padding:14px 18px;flex:1;overflow-y:auto;">
          <input type="text" id="customerSearch" class="search-input" placeholder="Type customer name..." style="min-width:0;width:100%;margin-bottom:8px;" autocomplete="off">
          <div id="customerDropdown" class="product-dropdown" style="position:relative;top:0;margin-bottom:10px;"></div>
          <div id="cartCustomer"></div>
        </div>
        <div class="payment-panel" style="padding:14px 18px;border-top:1px solid var(--border);">
          <div class="payment-heading" style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:800;margin-bottom:10px;">Payment</div>
          <div class="payment-methods" id="paymentMethods" style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px;">
            <button class="active" data-method="cash" onclick="setPayment('cash',this)" style="padding:10px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;color:var(--text);"><i class="fas fa-money-bill"></i> Cash</button>
            <button data-method="card" onclick="setPayment('card',this)" style="padding:10px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;color:var(--text);"><i class="fas fa-credit-card"></i> Card</button>
            <button data-method="pos" onclick="setPayment('pos',this)" style="padding:10px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;color:var(--text);"><i class="fas fa-cash-register"></i> POS</button>
            <button data-method="bank_transfer" onclick="setPayment('bank_transfer',this)" style="padding:10px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;color:var(--text);"><i class="fas fa-building-columns"></i> Transfer</button>
            <button data-method="store_account" onclick="setPayment('store_account',this)" style="padding:10px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;color:var(--text);"><i class="fas fa-wallet"></i> Account</button>
            <button data-method="giftcard" onclick="setPayment('giftcard',this)" style="padding:10px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;color:var(--text);"><i class="fas fa-gift"></i> Gift</button>
          </div>
          <input type="hidden" id="paymentMethod" value="cash">
          <input type="text" id="amountTendered" placeholder="Amount tendered (₦)" oninput="updateChange()" style="width:100%;padding:12px;border:1px solid var(--border);border-radius:10px;font-size:14px;margin-bottom:10px;outline:none;">
          <div class="quick-tender" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px;">
            <button onclick="quickTender(500)" style="padding:8px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">₦500</button>
            <button onclick="quickTender(1000)" style="padding:8px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">₦1K</button>
            <button onclick="quickTender(5000)" style="padding:8px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">₦5K</button>
            <button onclick="quickTender(10000)" style="padding:8px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">₦10K</button>
            <button onclick="quickTender(20000)" style="padding:8px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">₦20K</button>
            <button onclick="quickTender(50000)" style="padding:8px;border:1px solid var(--border);background:#fff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">₦50K</button>
          </div>
          <div id="changeRow" style="display:none;text-align:right;font-size:13px;color:var(--primary);font-weight:700;margin-bottom:8px;">Change: <span id="changeAmount">₦0.00</span></div>
          <button class="btn btn-sale" onclick="checkout()" style="width:100%;padding:14px;font-size:14px;border-radius:10px;margin-top:8px;"><i class="fas fa-check-circle"></i> Complete Sale</button>
        </div>
      </div>
    </div>
    <div style="padding:10px 18px;text-align:center;border-top:1px solid var(--border);background:transparent;margin-top:8px;">
      <a href="#" onclick="toggleShortcuts()" style="font-size:12px;color:var(--primary);font-weight:700;text-decoration:none;"><i class="fas fa-keyboard"></i> Keyboard shortcuts help</a>
    </div>
  </div>
</div>"""

    s = s[:start_idx] + new_layout + s[end_idx:]
    p.write_text(s, encoding='utf-8')
    print('OK: replaced pos-wrap layout')
else:
    print('NOT FOUND: pos-wrap markers')
