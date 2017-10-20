# coding: UTF-8

from flask import Flask, jsonify, request
from time import time
from urllib.parse import urlparse
from uuid import uuid4
import hashlib
import json
import requests

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []

        self.nodes = set()

        # genesic block
        self.new_block(previous_hash =1, proof=100)

    def register_node(self, address):
        """
        :param address: <str> node address. e.g.) http://192.168.0.5:5000
        :return Nonde
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def proof_of_work(self, last_proof):
        """
        :param last_proof: <int>
        : return: <int> proof
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        :param last_proof: <int> previous proof
        :param proof: <int> trying proof
        : return: <bool>
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == "0000"

    def new_block(self, proof, previous_hash=None):
        """
        : param proof: <int> The proof given by `Proof of work` algorithm
        : param previous_hash: (Optional) <str> Hash of previous block
        : return: <dict> New block
        """

        block = {
                'index': len(self.chain) + 1,
                'timestamp': time(),
                'transactions': self.current_transactions,
                'proof': proof,
                'previous_hash': previous_hash or self.hash(self.chain[-1])
                }
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        : param sender: <str> Address of the sender
        : param recipient: <str> Address of the recipient
        : param amount: <int> amount to send
        : return: <int> The index for this transactions
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        });

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        : param block: <dict> block
        : return: <str> SHA256 hash
        """

        # JSON keys should be sorted to calculate hash consistently.
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def valid_chain(self, chain):
        """
        Verify blockchain

        :param chain: <list> blockchain
        :return: <bool>
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')

            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Replace own chain with the longest chain
        : return <bool> replaced or not
        """

        neighbors = self.nodes
        new_chain = None

        max_length = len(self.nodes)

        for node in neighbors:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

app = Flask(__name__)

node_identifire = str(uuid4()).replace('-', '')
blockchain = Blockchain()

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'A block {index} added into the transaction'}
    return jsonify(response), 201

@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
            sender="0",
            recipient=node_identifire,
            amount=1,
     )

    block = blockchain.new_block(proof)
    response = {
        'message': 'Mined a new block',
        'index': block['index'],
        'transactions': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response), 200

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
            'chain': blockchain.chain,
            'length': len(blockchain.chain),
            }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_node():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Invalid node", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'A new node is added',
        'total_nodes': list(blockchain.nodes),
        }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consesus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
                'message': 'The chain is replaced',
                'new_chain': blockchain.chain,
                }
    else:
        response = {
                'message': 'The chain is confirmed',
                'chain': blockchain.chain,
                }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
