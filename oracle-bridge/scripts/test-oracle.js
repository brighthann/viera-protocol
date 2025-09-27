// Test script for oracle functionality
const { VieraOracleService } = require('../src/index.js');
const axios = require('axios');

async function testOracleService() {
    console.log('🧪 Testing Oracle Bridge Service...');
    
    try {
        // Test AI service connection
        console.log('1. Testing AI service connection...');
        const aiHealth = await axios.get('http://localhost:8000/health');
        console.log('✅ AI service healthy:', aiHealth.data.status);
        
        // Test oracle bridge health
        console.log('2. Testing oracle bridge health...');
        const oracleHealth = await axios.get('http://localhost:3001/health');
        console.log('✅ Oracle bridge healthy:', oracleHealth.data);
        
        // Test IPFS connectivity (with a known hash)
        console.log('3. Testing IPFS connectivity...');
        const testHash = 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'; // "hello world"
        const ipfsResponse = await axios.get(`https://ipfs.io/ipfs/${testHash}`, {
            timeout: 10000
        });
        console.log('✅ IPFS connectivity working');
        
        console.log('\n🎉 All tests passed! Oracle bridge is ready.');
        
    } catch (error) {
        console.error('❌ Test failed:', error.message);
        process.exit(1);
    }
}

testOracleService();