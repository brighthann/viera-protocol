// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IVieraProtocol {
    function validateMilestone(
        uint256 _milestoneId,
        bool _approved,
        uint8 _confidenceScore,
        string memory _validationReport
    ) external;
}

/**
 * @title VieraOracle
 * @dev Oracle contract that interfaces between AI validation service and main protocol
 * @notice Handles validation requests and forwards results to main contract
 */
contract VieraOracle is Ownable, ReentrancyGuard {
    
    // ============ State Variables ============
    
    struct ValidationJob {
        uint256 milestoneId;
        string contentHash;
        address requester;
        uint256 requestedAt;
        bool isCompleted;
        bool result;
        uint8 confidence;
        string report;
    }
    
    struct OracleNode {
        address nodeAddress;
        bool isActive;
        uint256 stake;
        uint256 completedJobs;
        uint256 accuracy; // Percentage accuracy based on consensus
        uint256 joinedAt;
    }
    
    // ============ Storage ============
    
    mapping(uint256 => ValidationJob) public validationJobs;
    mapping(address => OracleNode) public oracleNodes;
    mapping(uint256 => mapping(address => bool)) public nodeResponses; // jobId => node => hasResponded
    mapping(uint256 => address[]) public jobResponseNodes; // Track which nodes responded to each job
    
    IVieraProtocol public vieraProtocol;
    
    uint256 public nextJobId = 1;
    uint256 public minimumStake = 1 ether;
    uint256 public requiredConsensus = 3; // Minimum nodes needed for consensus
    uint256 public consensusThreshold = 66; // 66% agreement required
    
    address[] public activeNodes;
    
    // ============ Events ============
    
    event ValidationRequested(
        uint256 indexed jobId,
        uint256 indexed milestoneId,
        string contentHash,
        address requester
    );
    
    event NodeResponseSubmitted(
        uint256 indexed jobId,
        address indexed node,
        bool result,
        uint8 confidence
    );
    
    event ValidationCompleted(
        uint256 indexed jobId,
        uint256 indexed milestoneId,
        bool finalResult,
        uint8 finalConfidence
    );
    
    event NodeRegistered(address indexed node, uint256 stake);
    event NodeSlashed(address indexed node, uint256 amount, string reason);
    
    // ============ Modifiers ============
    
    modifier onlyActiveNode() {
        require(oracleNodes[msg.sender].isActive, "Not an active oracle node");
        _;
    }
    
    modifier onlyProtocol() {
        require(msg.sender == address(vieraProtocol), "Only protocol can call");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(address _vieraProtocol) Ownable(msg.sender) {
        vieraProtocol = IVieraProtocol(_vieraProtocol);
    }
    
    // ============ Oracle Node Management ============
    
    /**
     * @dev Register as an oracle node with stake
     */
    function registerNode() external payable {
        require(msg.value >= minimumStake, "Insufficient stake");
        require(!oracleNodes[msg.sender].isActive, "Already registered");
        
        oracleNodes[msg.sender] = OracleNode({
            nodeAddress: msg.sender,
            isActive: true,
            stake: msg.value,
            completedJobs: 0,
            accuracy: 100, // Start with perfect accuracy
            joinedAt: block.timestamp
        });
        
        activeNodes.push(msg.sender);
        
        emit NodeRegistered(msg.sender, msg.value);
    }
    
    /**
     * @dev Unregister node and withdraw stake
     */
    function unregisterNode() external nonReentrant {
        OracleNode storage node = oracleNodes[msg.sender];
        require(node.isActive, "Not an active node");
        
        uint256 stakeAmount = node.stake;
        node.isActive = false;
        node.stake = 0;
        
        // Remove from active nodes array
        for (uint256 i = 0; i < activeNodes.length; i++) {
            if (activeNodes[i] == msg.sender) {
                activeNodes[i] = activeNodes[activeNodes.length - 1];
                activeNodes.pop();
                break;
            }
        }
        
        payable(msg.sender).transfer(stakeAmount);
    }
    
    /**
     * @dev Add additional stake
     */
    function addStake() external payable onlyActiveNode {
        oracleNodes[msg.sender].stake += msg.value;
    }
    
    // ============ Validation Functions ============
    
    /**
     * @dev Request validation from oracle network
     */
    function requestValidation(
        uint256 _milestoneId,
        string memory _contentHash
    ) external onlyProtocol returns (uint256) {
        uint256 jobId = nextJobId++;
        
        validationJobs[jobId] = ValidationJob({
            milestoneId: _milestoneId,
            contentHash: _contentHash,
            requester: msg.sender,
            requestedAt: block.timestamp,
            isCompleted: false,
            result: false,
            confidence: 0,
            report: ""
        });
        
        emit ValidationRequested(jobId, _milestoneId, _contentHash, msg.sender);
        return jobId;
    }
    
    /**
     * @dev Oracle node submits validation response
     */
    function submitValidation(
        uint256 _jobId,
        bool _result,
        uint8 _confidence,
        string memory _report
    ) external onlyActiveNode {
        require(validationJobs[_jobId].requestedAt > 0, "Job does not exist");
        require(!validationJobs[_jobId].isCompleted, "Job already completed");
        require(!nodeResponses[_jobId][msg.sender], "Already responded");
        require(_confidence <= 100, "Invalid confidence");
        
        nodeResponses[_jobId][msg.sender] = true;
        jobResponseNodes[_jobId].push(msg.sender);
        
        // Store response (simplified - in production, you'd store all responses)
        ValidationJob storage job = validationJobs[_jobId];
        
        emit NodeResponseSubmitted(_jobId, msg.sender, _result, _confidence);
        
        // Check if we have enough responses for consensus
        if (jobResponseNodes[_jobId].length >= requiredConsensus) {
            _processConsensus(_jobId);
        }
    }
    
    /**
     * @dev Process consensus from oracle responses
     */
    function _processConsensus(uint256 _jobId) internal {
        ValidationJob storage job = validationJobs[_jobId];
        address[] memory respondingNodes = jobResponseNodes[_jobId];
        
        uint256 approvalCount = 0;
        uint256 totalConfidence = 0;
        uint256 responseCount = respondingNodes.length;
        
        // Simple consensus - count approvals and average confidence
        // In production, you'd want more sophisticated consensus mechanisms
        for (uint256 i = 0; i < responseCount; i++) {
            // This is simplified - in reality you'd store individual responses
            // For MVP, we'll use the last response as representative
            approvalCount++; // Placeholder
            totalConfidence += 80; // Placeholder
        }
        
        uint256 approvalPercentage = (approvalCount * 100) / responseCount;
        bool consensusResult = approvalPercentage >= consensusThreshold;
        uint8 avgConfidence = uint8(totalConfidence / responseCount);
        
        job.isCompleted = true;
        job.result = consensusResult;
        job.confidence = avgConfidence;
        job.report = "consensus-report"; // Simplified for MVP
        
        // Update node statistics
        for (uint256 i = 0; i < responseCount; i++) {
            oracleNodes[respondingNodes[i]].completedJobs++;
        }
        
        // Forward result to main protocol
        vieraProtocol.validateMilestone(
            job.milestoneId,
            consensusResult,
            avgConfidence,
            job.report
        );
        
        emit ValidationCompleted(_jobId, job.milestoneId, consensusResult, avgConfidence);
    }
    
    // ============ Admin Functions ============
    
    function setMinimumStake(uint256 _stake) external onlyOwner {
        minimumStake = _stake;
    }
    
    function setConsensusRequirements(uint256 _required, uint256 _threshold) external onlyOwner {
        require(_threshold > 50 && _threshold <= 100, "Invalid threshold");
        requiredConsensus = _required;
        consensusThreshold = _threshold;
    }
    
    function slashNode(address _node, uint256 _amount, string memory _reason) external onlyOwner {
        OracleNode storage node = oracleNodes[_node];
        require(node.isActive, "Node not active");
        require(_amount <= node.stake, "Amount exceeds stake");
        
        node.stake -= _amount;
        
        if (node.stake < minimumStake) {
            node.isActive = false;
            // Remove from active nodes
            for (uint256 i = 0; i < activeNodes.length; i++) {
                if (activeNodes[i] == _node) {
                    activeNodes[i] = activeNodes[activeNodes.length - 1];
                    activeNodes.pop();
                    break;
                }
            }
        }
        
        // Send slashed amount to protocol treasury
        payable(owner()).transfer(_amount);
        
        emit NodeSlashed(_node, _amount, _reason);
    }
    
    // ============ View Functions ============
    
    function getActiveNodes() external view returns (address[] memory) {
        return activeNodes;
    }
    
    function getJobDetails(uint256 _jobId) external view returns (ValidationJob memory) {
        return validationJobs[_jobId];
    }
    
    function getNodeInfo(address _node) external view returns (OracleNode memory) {
        return oracleNodes[_node];
    }
    
    function getPendingJobs() external view returns (uint256[] memory) {
        uint256[] memory pending = new uint256[](nextJobId - 1);
        uint256 count = 0;
        
        for (uint256 i = 1; i < nextJobId; i++) {
            if (!validationJobs[i].isCompleted && validationJobs[i].requestedAt > 0) {
                pending[count] = i;
                count++;
            }
        }
        
        uint256[] memory result = new uint256[](count);
        for (uint256 j = 0; j < count; j++) {
            result[j] = pending[j];
        }
        
        return result;
    }
}