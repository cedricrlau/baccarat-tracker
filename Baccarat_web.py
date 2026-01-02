import streamlit as st
import pandas as pd

# --- BACKEND LOGIC ---
class BaccaratEngine:
    def __init__(self):
        self.players = {}          # {name: balance}
        self.player_order = []     # Seating order
        self.current_banker_idx = 0 
        self.start_balance = 10000.0
        
        # Settings
        self.commission_rate = 0.05
        self.payout_tie = 8.0
        self.payout_super6 = 0.5    
        self.payout_dragon7 = 40.0  
        self.payout_panda8 = 25.0   
        self.game_mode = "Punto Banco"
        
        self.chips = [(1000, 'Black'), (100, 'Green'), (25, 'Blue'), (5, 'Red'), (1, 'White')]

    def get_chip_breakdown(self, amount):
        if amount <= 0: return ""
        cents = int(round(amount * 100))
        breakdown = []
        for val, color in self.chips:
            chip_cents = int(val * 100)
            count = cents // chip_cents
            if count > 0:
                breakdown.append(f"{count}x {color}")
                cents %= chip_cents
        if cents > 0:
            breakdown.append(f"${cents/100:.2f} (Coins)")
        return ", ".join(breakdown)

    def pass_shoe(self):
        if not self.player_order: return
        self.current_banker_idx = (self.current_banker_idx + 1) % len(self.player_order)
        return self.player_order[self.current_banker_idx]

    def get_current_banker(self):
        if not self.player_order: return "The House"
        if self.game_mode == "Chemin de Fer":
            return self.player_order[self.current_banker_idx]
        return "The House"

    def calculate_auto_fix(self, bets, bank_limit):
        active_banker = self.get_current_banker()
        punter_bets_ordered = [] 
        total_wagered = 0.0
        
        for name in self.player_order:
            if name == active_banker: continue
            if name in bets:
                amt = bets[name].get('amount', 0.0)
                punter_bets_ordered.append({'name': name, 'amount': amt, 'data': bets[name]})
                total_wagered += amt

        excess = total_wagered - bank_limit
        if excess <= 0: return bets

        new_bets = bets.copy()
        for i in range(len(punter_bets_ordered) - 1, -1, -1):
            if excess <= 0: break
            p_data = punter_bets_ordered[i]
            current_amt = p_data['amount']
            name = p_data['name']
            
            deduct = min(current_amt, excess)
            new_amt = current_amt - deduct
            new_bets[name]['amount'] = new_amt if new_amt > 0 else 0.0
            excess -= deduct
        return new_bets

    def calculate_round(self, bets, winner, special_trigger, bank_limit=0.0):
        results = []
        active_banker = self.get_current_banker()
        
        banker_gross_win = 0.0
        banker_net_win = 0.0
        banker_pnl = 0.0 
        
        for player, bet_data in bets.items():
            if player == active_banker: continue 
            side = bet_data.get('side', '')
            amount = bet_data.get('amount', 0.0)
            if amount <= 0: continue

            winnings = 0.0
            outcome_txt = ""

            # 1. TIE
            if winner == 'T':
                if side == 'T':
                    profit = amount * self.payout_tie
                    winnings = profit + amount
                    self.players[player] += profit
                    if active_banker != "The House": banker_pnl -= profit
                    outcome_txt = f"WON Tie (+${profit:.0f})"
                else:
                    outcome_txt = "PUSH (Tie)"
            
            # 2. MATCHING WINNER
            elif side == winner:
                profit = 0.0
                if side == 'P':
                    if self.game_mode == "Panda 8" and special_trigger:
                        profit = amount * self.payout_panda8
                    else:
                        profit = amount
                elif side == 'B':
                    if self.game_mode == "Super 6":
                        profit = amount * self.payout_super6 if special_trigger else amount
                    elif self.game_mode == "EZ Baccarat":
                        if special_trigger:
                            profit = 0.0
                            outcome_txt = "PUSH (Dragon 7)"
                        else:
                            profit = amount
                    elif self.game_mode == "Dragon 7":
                        if special_trigger:
                            profit = amount * self.payout_dragon7
                        else:
                            profit = amount
                    else:
                        profit = amount - (amount * self.commission_rate)

                is_push = (outcome_txt == "PUSH (Dragon 7)")
                if not is_push:
                    winnings = profit + amount
                    self.players[player] += profit
                    if active_banker != "The House": banker_pnl -= profit
                    outcome_txt = f"WON (+${profit:.2f})"
            
            # 3. LOSER
            else:
                self.players[player] -= amount
                if active_banker != "The House": banker_pnl += amount
                outcome_txt = f"LOST (-${amount:.0f})"

            res_str = f"**{player}**: {outcome_txt}"
            if winnings > 0:
                chips = self.get_chip_breakdown(winnings)
                res_str += f" -> *Pay: {chips}*"
            results.append(res_str)

        if active_banker != "The House":
            bnk_res = f"**BANKER ({active_banker})**: "
            if banker_pnl > 0:
                if self.game_mode in ["EZ Baccarat", "Super 6", "Dragon 7", "Panda 8"]:
                    comm = 0.0
                else:
                    comm = banker_pnl * self.commission_rate
                net = banker_pnl - comm
                banker_gross_win = banker_pnl
                banker_net_win = net
                self.players[active_banker] += net
                bnk_res += f"WON (+${net:.2f}) [Gross: {banker_pnl} - Comm: {comm}]"
            elif banker_pnl < 0:
                banker_net_win = banker_pnl
                self.players[active_banker] += banker_pnl
                bnk_res += f"LOST (-${abs(banker_pnl):.0f})"
            else:
                bnk_res += "EVEN"
            results.insert(0, bnk_res)

        return results, banker_gross_win, banker_net_win

# --- STREAMLIT FRONTEND ---
st.set_page_config(page_title="Baccarat Tracker", page_icon="♠️", layout="wide")

if 'engine' not in st.session_state:
    st.session_state.engine = BaccaratEngine()
if 'game_active' not in st.session_state:
    st.session_state.game_active = False
if 'bank_limit' not in st.session_state:
    st.session_state.bank_limit = 0.0
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'verified' not in st.session_state:
    st.session_state.verified = False

def add_log(msg):
    st.session_state.logs.insert(0, msg)

# --- SETUP SCREEN ---
if not st.session_state.game_active:
    st.title("♠️ Baccarat Table Setup")
    
    with st.expander("Configuration", expanded=True):
        buyin = st.number_input("Buy-In Amount ($)", value=10000.0, step=100.0)
        names_str = st.text_input("Player Names (Comma Separated)", "Player 1, Player 2, Player 3")
        
    with st.expander("Rules & Modes", expanded=True):
        mode = st.selectbox("Game Mode", ["Punto Banco", "Chemin de Fer", "Super 6", "EZ Baccarat", "Dragon 7", "Panda 8"])
        tie_pay = st.number_input("Tie Payout (X:1)", value=8.0)
        comm_pct = st.number_input("Commission (%)", value=5.0)
        
        special_pay = 0.0
        if mode == "Super 6":
            special_pay = st.number_input("Banker 6 Payout (0.5 = 50%)", value=0.5)
        elif mode == "Dragon 7":
            special_pay = st.number_input("Dragon 7 Payout", value=40.0)
        elif mode == "Panda 8":
            special_pay = st.number_input("Panda 8 Payout", value=25.0)

    if st.button("OPEN TABLE", type="primary"):
        eng = st.session_state.engine
        eng.start_balance = buyin
        eng.commission_rate = comm_pct / 100.0
        eng.payout_tie = tie_pay
        eng.game_mode = mode
        
        if mode == "Super 6":
            eng.payout_super6 = special_pay
            eng.commission_rate = 0.0
        elif mode == "Dragon 7":
            eng.payout_dragon7 = special_pay
            eng.commission_rate = 0.0
        elif mode == "Panda 8":
            eng.payout_panda8 = special_pay
            eng.commission_rate = 0.0
        elif mode == "EZ Baccarat":
            eng.commission_rate = 0.0
            
        names = [n.strip() for n in names_str.split(',') if n.strip()]
        eng.players = {n: buyin for n in names}
        eng.player_order = names
        eng.current_banker_idx = 0
        
        st.session_state.bank_limit = buyin
        st.session_state.game_active = True
        st.session_state.logs = [f"=== {mode.upper()} STARTED ==="]
        st.rerun()

# --- GAME SCREEN ---
else:
    eng = st.session_state.engine
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("⬅ Setup"):
            st.session_state.game_active = False
            st.rerun()
    with col2:
        st.header(f"Mode: {eng.game_mode}")

    if eng.game_mode == "Chemin de Fer":
        st.info(f"**Banker:** {eng.get_current_banker()}")
        b_col1, b_col2, b_col3, b_col4 = st.columns([2, 2, 2, 2])
        with b_col1:
            st.session_state.bank_limit = st.number_input("Bank Limit", value=st.session_state.bank_limit, step=100.0)
        with b_col2:
            inc_comm = st.checkbox("Inc. Comm in Limit?", value=False)
        with b_col3:
            if st.button("Pass Shoe"):
                new_bnk = eng.pass_shoe()
                add_log(f"--- SHOE PASSED TO {new_bnk} ---")
                st.rerun()

    st.subheader("Chips")
    score_cols = st.columns(len(eng.player_order))
    for i, name in enumerate(eng.player_order):
        bal = eng.players[name]
        with score_cols[i]:
            st.metric(label=name, value=f"${bal:.0f}")

    st.markdown("---")

    st.subheader("Place Bets")
    current_bets = {}
    active_banker = eng.get_current_banker()
    
    for name in eng.player_order:
        is_banker = (name == active_banker and eng.game_mode == "Chemin de Fer")
        
        with st.container():
            c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
            with c1:
                st.write(f"**{name}**" + (" (BNK)" if is_banker else ""))
            with c2:
                side = st.radio("Side", ["-", "B", "P", "T"], horizontal=True, key=f"side_{name}", label_visibility="collapsed", disabled=is_banker)
            with c3:
                amt = st.number_input("Amount", min_value=0.0, step=10.0, key=f"amt_{name}", label_visibility="collapsed", disabled=is_banker)
            
            if eng.game_mode == "Chemin de Fer" and not is_banker:
                with c4:
                    st.button("BANCO!", key=f"banco_{name}", disabled=True, help="Type amount manually for now")
            
            if side != "-" and amt > 0:
                current_bets[name] = {'side': side, 'amount': amt}

    st.markdown("---")

    if st.button("VERIFY BETS", type="secondary", use_container_width=True):
        total_wager = sum(b['amount'] for b in current_bets.values())
        limit = st.session_state.bank_limit
        
        if eng.game_mode == "Chemin de Fer" and total_wager > limit:
            st.error(f"⚠️ Bets (${total_wager}) exceed Bank Limit (${limit})!")
            st.warning("Please reduce bets manually based on Reverse Seating Order.")
        else:
            st.success("✅ Bets Valid!")
            st.session_state.verified = True

    st.write("### Result")
    r_col1, r_col2, r_col3, r_col4 = st.columns([1, 1, 1, 1])
    
    trigger = False
    with r_col4:
        if eng.game_mode == "Super 6": trigger = st.checkbox("Banker 6?")
        elif eng.game_mode == "EZ Baccarat": trigger = st.checkbox("Dragon 7?")
        elif eng.game_mode == "Dragon 7": trigger = st.checkbox("Dragon 7?")
        elif eng.game_mode == "Panda 8": trigger = st.checkbox("Panda 8?")

    winner = None
    if r_col1.button("BANKER WIN", type="primary"): winner = 'B'
    if r_col2.button("PLAYER WIN", type="primary"): winner = 'P'
    if r_col3.button("TIE", type="secondary"): winner = 'T'

    if winner:
        limit = st.session_state.bank_limit
        total_wager = sum(b['amount'] for b in current_bets.values())
        
        if eng.game_mode == "Chemin de Fer" and total_wager > limit:
             st.error("Cannot process: Bets exceed limit! Verify first.")
        else:
            results, b_gross, b_net = eng.calculate_round(current_bets, winner, trigger, 0)
            
            w_txt = f"WINNER: {winner}"
            if trigger: w_txt += " (Special Rule Triggered)"
            add_log(w_txt)
            for r in results: add_log(r)
            add_log("-" * 30)
            
            if eng.game_mode == "Chemin de Fer":
                if winner == 'P':
                    add_log(">> Player Won. Shoe passing...")
                    eng.pass_shoe()
                elif winner == 'B':
                    add_log(">> Banker Won. Shoe remains.")
                    if b_gross > 0:
                         # 'inc_comm' exists in local scope if Chemmy is active
                         try:
                             add_amt = b_net if inc_comm else b_gross
                             st.session_state.bank_limit += add_amt
                             add_log(f"   [Bank Limit increased to ${st.session_state.bank_limit:.0f}]")
                         except: pass
            
            st.rerun()

    st.markdown("### Activity Log")
    log_box = st.container(height=300)
    for line in st.session_state.logs:
        log_box.write(line)
