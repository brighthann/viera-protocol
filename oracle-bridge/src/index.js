// oracle-bridge/src/index.js - Fixed version with nonce management
const { ethers } = require('ethers');
const axios = require('axios');
const winston = require('winston');
const cron = require('node-cron');
const express = require('express');
require('dotenv').config();

class VieraOracleService {
    constructor() {
        this.setupLogger();
        this.setupBlockchain();
        this.setupServices();
        this.isProcessing = false;
        this.failedJobs = new Map();
        this.retryCount = new Map();
        this.currentNonce = null; // Track nonce manually
        
        // Configuration
        this.config = {
            AI_SERVICE_URL: process.env.AI_SERVICE_URL || 'http://localhost:8000',
            IPFS_GATEWAY: process.env.IPFS_GATEWAY || 'https://ipfs.io/ipfs/',
            MAX_RETRIES: parseInt(process.env.MAX_RETRIES) || 3,
            RETRY_DELAY_MS: parseInt(process.env.RETRY_DELAY_MS) || 5000,
            POLL_INTERVAL_MS: parseInt(process.env.POLL_INTERVAL_MS) || 10000,
            BACKUP_IPFS_GATEWAYS: [
                'https://gateway.pinata.cloud/ipfs/',
                'https://cloudflare-ipfs.com/ipfs/',
                'https://dweb.link/ipfs/'
            ]
        };
    }

    setupLogger() {
        this.logger = winston.createLogger({
            level: 'info',
            format: winston.format.combine(
                winston.format.timestamp(),
                winston.format.errors({ stack: true }),
                winston.format.json()
            ),
            transports: [
                new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
                new winston.transports.File({ filename: 'logs/combined.log' }),
                new winston.transports.Console({
                    format: winston.format.simple()
                })
            ]
        });
    }

    setupBlockchain() {
        try {
            // Connect to blockchain
            this.provider = new ethers.JsonRpcProvider(process.env.RPC_URL);
            this.wallet = new ethers.Wallet(process.env.PRIVATE_KEY, this.provider);
            
            // Initialize contracts
            this.protocolContract = new ethers.Contract(
                process.env.VIERA_PROTOCOL_ADDRESS,
                require('./abis/VieraProtocol.json'),
                this.wallet
            );
            
            this.oracleContract = new ethers.Contract(
                process.env.VIERA_ORACLE_ADDRESS,
                require('./abis/VieraOracle.json'),
                this.wallet
            );

            this.logger.info('Blockchain connection established', {
                network: process.env.NETWORK || 'localhost',
                wallet: this.wallet.address
            });
        } catch (error) {
            this.logger.error('Failed to setup blockchain connection', error);
            throw error;
        }
    }

    setupServices() {
        // Express server for health checks and manual operations
        this.app = express();
        this.app.use(express.json());
        
        this.app.get('/health', (req, res) => {
            res.json({
                status: 'running',
                wallet: this.wallet.address,
                isProcessing: this.isProcessing,
                failedJobs: this.failedJobs.size,
                currentNonce: this.currentNonce
            });
        });

        this.app.post('/manual/validate/:milestoneId', async (req, res) => {
            try {
                const result = await this.processValidationRequest(req.params.milestoneId, true);
                res.json({ success: true, result });
            } catch (error) {
                res.status(500).json({ success: false, error: error.message });
            }
        });

        const port = process.env.PORT || 3001;
        this.app.listen(port, () => {
            this.logger.info(`Oracle bridge server running on port ${port}`);
        });
    }

    async initializeNonce() {
        try {
            this.currentNonce = await this.provider.getTransactionCount(this.wallet.address, 'pending');
            this.logger.info('Nonce initialized', { nonce: this.currentNonce });
        } catch (error) {
            this.logger.error('Failed to initialize nonce', error);
            this.currentNonce = 0;
        }
    }

    async getNextNonce() {
        if (this.currentNonce === null) {
            await this.initializeNonce();
        }
        return this.currentNonce++;
    }

    async sendTransactionWithRetry(contractMethod, ...args) {
        const maxAttempts = 3;
        
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                const nonce = await this.getNextNonce();
                
                this.logger.debug('Sending transaction', {
                    attempt,
                    nonce,
                    method: contractMethod.name || 'unknown'
                });
                
                const tx = await contractMethod(...args, {
                    nonce: nonce,
                    gasLimit: 500000, // Set explicit gas limit
                    gasPrice: ethers.parseUnits('20', 'gwei') // Set explicit gas price
                });
                
                const receipt = await tx.wait();
                
                this.logger.info('Transaction successful', {
                    hash: receipt.hash,
                    nonce: nonce
                });
                
                return receipt;
                
            } catch (error) {
                this.logger.warn(`Transaction attempt ${attempt} failed`, {
                    error: error.message,
                    code: error.code
                });
                
                if (error.code === 'NONCE_EXPIRED' || error.message.includes('nonce')) {
                    // Reset nonce and try again
                    await this.initializeNonce();
                    continue;
                }
                
                if (attempt === maxAttempts) {
                    throw error;
                }
                
                // Wait before retry
                await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
            }
        }
    }

    async start() {
        this.logger.info('Starting Viera Oracle Service...');
        
        try {
            // Initialize nonce tracking
            await this.initializeNonce();
            
            // Register as oracle node if not already registered
            await this.ensureOracleRegistration();
            
            // Start monitoring blockchain
            this.startEventListener();
            
            // Start periodic health checks
            this.startHealthChecks();
            
            // Start retry processor
            this.startRetryProcessor();
            
            this.logger.info('Oracle service started successfully');
        } catch (error) {
            this.logger.error('Failed to start oracle service', error);
            throw error;
        }
    }

    async ensureOracleRegistration() {
        try {
            const nodeInfo = await this.oracleContract.getNodeInfo(this.wallet.address);
            
            if (!nodeInfo.isActive) {
                this.logger.info('Registering as oracle node...');
                
                const receipt = await this.sendTransactionWithRetry(
                    this.oracleContract.registerNode.bind(this.oracleContract),
                    { value: ethers.parseEther(process.env.ORACLE_STAKE || "1.0") }
                );
                
                this.logger.info('Successfully registered as oracle node', {
                    txHash: receipt.hash
                });
            } else {
                this.logger.info('Already registered as oracle node', {
                    stake: ethers.formatEther(nodeInfo.stake)
                });
            }
        } catch (error) {
            this.logger.error('Failed to ensure oracle registration', error);
            throw error;
        }
    }

    startEventListener() {
        // Listen for validation requests
        this.protocolContract.on('ValidationRequested', async (validationId, milestoneId, contentHash) => {
            this.logger.info('New validation request', {
                validationId: validationId.toString(),
                milestoneId: milestoneId.toString(),
                contentHash
            });

            try {
                await this.processValidationRequest(milestoneId, false);
            } catch (error) {
                this.logger.error('Failed to process validation request', {
                    milestoneId: milestoneId.toString(),
                    error: error.message
                });
                
                // Add to retry queue
                this.addToRetryQueue(milestoneId.toString(), error);
            }
        });

        this.logger.info('Event listener started');
    }

    async processValidationRequest(milestoneId, isRetry = false) {
        const startTime = Date.now();
        
        try {
            this.isProcessing = true;
            
            this.logger.info('Processing validation request', {
                milestoneId: milestoneId.toString(),
                isRetry
            });

            // 1. Get milestone details from contract
            const milestone = await this.protocolContract.getMilestone(milestoneId);
            
            if (milestone.status !== 2) { // Not in AI_VALIDATING status
                throw new Error(`Invalid milestone status: ${milestone.status}`);
            }

            // 2. Fetch file from IPFS
            const fileData = await this.fetchFromIPFS(milestone.ipfsHash);
            
            // 3. Determine researcher type and prepare validation request
            const researcherInfo = await this.protocolContract.getResearcherStats(milestone.researcher);
            const validationRequest = this.prepareValidationRequest(milestone, fileData, researcherInfo);
            
            // 4. Send to AI service
            const aiResult = await this.callAIService(validationRequest);
            
            // 5. Submit result to blockchain
            const txResult = await this.submitValidationResult(milestoneId, aiResult);
            
            const processingTime = Date.now() - startTime;
            
            this.logger.info('Validation completed successfully', {
                milestoneId: milestoneId.toString(),
                confidence: aiResult.overall_confidence,
                recommendation: aiResult.recommendation,
                processingTimeMs: processingTime,
                txHash: txResult.hash
            });

            // Remove from retry queue if it was there
            this.retryCount.delete(milestoneId.toString());
            this.failedJobs.delete(milestoneId.toString());

            return {
                success: true,
                confidence: aiResult.overall_confidence,
                recommendation: aiResult.recommendation,
                txHash: txResult.hash
            };

        } catch (error) {
            this.logger.error('Validation processing failed', {
                milestoneId: milestoneId.toString(),
                error: error.message,
                stack: error.stack
            });
            
            throw error;
        } finally {
            this.isProcessing = false;
        }
    }

    async submitValidationResult(milestoneId, aiResult) {
        try {
            this.logger.debug('Submitting validation result to blockchain', {
                milestoneId: milestoneId.toString(),
                confidence: aiResult.overall_confidence,
                recommendation: aiResult.recommendation
            });
            
            // Map AI recommendation to boolean approval
            const approved = aiResult.recommendation === 'approve';
            
            // Submit through oracle contract using retry mechanism
            const receipt = await this.sendTransactionWithRetry(
                this.oracleContract.submitValidation.bind(this.oracleContract),
                milestoneId,
                approved,
                aiResult.overall_confidence,
                aiResult.validation_id || 'ai_validation_report'
            );
            
            this.logger.info('Validation result submitted to blockchain', {
                milestoneId: milestoneId.toString(),
                txHash: receipt.hash,
                approved,
                confidence: aiResult.overall_confidence
            });
            
            return receipt;
            
        } catch (error) {
            this.logger.error('Failed to submit validation result', {
                milestoneId: milestoneId.toString(),
                error: error.message
            });
            throw error;
        }
    }

    // ... [Rest of the methods remain the same as before]
    // Including: fetchFromIPFS, prepareValidationRequest, callAIService, 
    // addToRetryQueue, startRetryProcessor, startHealthChecks

    async fetchFromIPFS(ipfsHash) {
        const gateways = [this.config.IPFS_GATEWAY, ...this.config.BACKUP_IPFS_GATEWAYS];
        
        for (let i = 0; i < gateways.length; i++) {
            try {
                const url = `${gateways[i]}${ipfsHash}`;
                this.logger.debug('Fetching from IPFS', { url });
                
                const response = await axios.get(url, {
                    timeout: 30000,
                    maxContentLength: 100 * 1024 * 1024,
                    responseType: 'arraybuffer'
                });
                
                this.logger.info('Successfully fetched from IPFS', {
                    ipfsHash,
                    gateway: gateways[i],
                    sizeBytes: response.data.length
                });
                
                return {
                    content: response.data,
                    contentType: response.headers['content-type'] || 'application/octet-stream',
                    size: response.data.length
                };
                
            } catch (error) {
                this.logger.warn('IPFS gateway failed', {
                    gateway: gateways[i],
                    error: error.message
                });
                
                if (i === gateways.length - 1) {
                    throw new Error(`Failed to fetch from IPFS after trying ${gateways.length} gateways`);
                }
            }
        }
    }

    prepareValidationRequest(milestone, fileData, researcherInfo) {
        let researcherType = 'coder';
        
        if (milestone.description.toLowerCase().includes('research') || 
            milestone.description.toLowerCase().includes('paper')) {
            researcherType = 'researcher';
        } else if (milestone.description.toLowerCase().includes('data') ||
                   milestone.description.toLowerCase().includes('analysis')) {
            researcherType = 'data_scientist';
        }

        return {
            submission_id: milestone.id.toString(),
            researcher_type: researcherType,
            milestone_description: milestone.description,
            file_data: fileData.content,
            file_info: {
                name: `milestone_${milestone.id}_submission`,
                type: fileData.contentType,
                size: fileData.size
            }
        };
    }

    async callAIService(validationRequest) {
        try {
            // For Node.js, we need to use a different approach for FormData
            const FormData = require('form-data');
            const formData = new FormData();
            
            formData.append('submission_id', validationRequest.submission_id);
            formData.append('researcher_type', validationRequest.researcher_type);
            formData.append('milestone_description', validationRequest.milestone_description);
            formData.append('files', validationRequest.file_data, {
                filename: validationRequest.file_info.name,
                contentType: validationRequest.file_info.type
            });
            
            this.logger.debug('Calling AI service', {
                url: `${this.config.AI_SERVICE_URL}/validate`,
                submissionId: validationRequest.submission_id
            });
            
            const response = await axios.post(
                `${this.config.AI_SERVICE_URL}/validate`,
                formData,
                {
                    headers: formData.getHeaders(),
                    timeout: 60000
                }
            );
            
            this.logger.info('AI service response received', {
                confidence: response.data.overall_confidence,
                recommendation: response.data.recommendation,
                issues: response.data.issues_found.length
            });
            
            return response.data;
            
        } catch (error) {
            if (error.response) {
                this.logger.error('AI service returned error', {
                    status: error.response.status,
                    data: error.response.data
                });
                throw new Error(`AI service error: ${error.response.status}`);
            } else if (error.request) {
                throw new Error('AI service not responding');
            } else {
                throw new Error(`AI service request failed: ${error.message}`);
            }
        }
    }

    addToRetryQueue(milestoneId, error) {
        const currentRetries = this.retryCount.get(milestoneId) || 0;
        
        if (currentRetries < this.config.MAX_RETRIES) {
            this.retryCount.set(milestoneId, currentRetries + 1);
            this.failedJobs.set(milestoneId, {
                error: error.message,
                retryCount: currentRetries + 1,
                nextRetry: Date.now() + (this.config.RETRY_DELAY_MS * Math.pow(2, currentRetries)),
                originalError: error.stack
            });
            
            this.logger.info('Added to retry queue', {
                milestoneId,
                retryCount: currentRetries + 1,
                maxRetries: this.config.MAX_RETRIES
            });
        } else {
            this.logger.error('Max retries exceeded', {
                milestoneId,
                retries: currentRetries
            });
        }
    }

    startRetryProcessor() {
        cron.schedule('* * * * *', async () => {
            const now = Date.now();
            
            for (const [milestoneId, jobInfo] of this.failedJobs.entries()) {
                if (now >= jobInfo.nextRetry && !this.isProcessing) {
                    this.logger.info('Retrying failed validation', {
                        milestoneId,
                        attempt: jobInfo.retryCount
                    });
                    
                    try {
                        await this.processValidationRequest(milestoneId, true);
                    } catch (error) {
                        this.addToRetryQueue(milestoneId, error);
                    }
                    
                    break;
                }
            }
        });
    }

    startHealthChecks() {
        cron.schedule('*/5 * * * *', async () => {
            try {
                const aiHealth = await axios.get(`${this.config.AI_SERVICE_URL}/health`, {
                    timeout: 5000
                });
                
                const blockNumber = await this.provider.getBlockNumber();
                const balance = await this.provider.getBalance(this.wallet.address);
                
                this.logger.info('Health check passed', {
                    aiService: aiHealth.data.status,
                    blockNumber,
                    walletBalance: ethers.formatEther(balance),
                    failedJobs: this.failedJobs.size,
                    currentNonce: this.currentNonce
                });
                
                if (balance < ethers.parseEther("0.1")) {
                    this.logger.warn('Low wallet balance detected', {
                        balance: ethers.formatEther(balance)
                    });
                }
                
            } catch (error) {
                this.logger.error('Health check failed', error);
            }
        });
    }
}

// Add form-data dependency installation
// Run: npm install form-data

async function main() {
    const oracle = new VieraOracleService();
    
    process.on('SIGINT', () => {
        console.log('Shutting down oracle service...');
        process.exit(0);
    });
    
    process.on('unhandledRejection', (reason, promise) => {
        console.error('Unhandled Rejection at:', promise, 'reason:', reason);
    });
    
    try {
        await oracle.start();
        console.log('Oracle service running. Press Ctrl+C to stop.');
    } catch (error) {
        console.error('Failed to start oracle service:', error);
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { VieraOracleService };