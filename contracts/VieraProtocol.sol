// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title VieraProtocol
 * @dev Core contract for decentralized research funding with AI-powered validation
 * @notice Manages milestone-based funding with automated payments
 */
contract VieraProtocol is ReentrancyGuard, Ownable, Pausable {
    
    // ============ State Variables ============
    
    struct Milestone {
        uint256 id;
        address researcher;
        address funder;
        uint256 amount;
        string ipfsHash;          // Research deliverables stored on IPFS
        string description;       // Milestone description
        uint256 deadline;         // Deadline timestamp
        MilestoneStatus status;
        uint256 submittedAt;      // When researcher submitted deliverables
        uint256 validatedAt;      // When AI oracle validated
        uint8 confidenceScore;    // AI confidence (0-100)
        string validationReport;  // IPFS hash of detailed AI analysis
    }
    
    enum MilestoneStatus {
        CREATED,          // Milestone created, funded
        SUBMITTED,        // Researcher submitted deliverables
        AI_VALIDATING,    // Oracle is validating
        APPROVED,         // AI approved with high confidence
        HUMAN_REVIEW,     // Requires human reviewer input
        PAID,             // Payment completed
        DISPUTED,         // In dispute resolution
        CANCELLED         // Cancelled/refunded
    }
    
    struct Researcher {
        address wallet;
        string profile;           // IPFS hash of researcher profile
        uint256 completedMilestones;
        uint256 totalEarned;
        uint256 reputationScore;  // 0-1000 scale
        bool isVerified;
    }
    
    struct Funder {
        address wallet;
        string profile;           // IPFS hash of funder profile
        uint256 totalFunded;
        uint256 activeMilestones;
        bool isInstitution;       // University/organization vs individual
    }
    
    struct ValidationRequest {
        uint256 milestoneId;
        string contentHash;       // IPFS hash of submission
        uint256 requestedAt;
        bool isProcessed;
    }
    
    // ============ Storage ============
    
    mapping(uint256 => Milestone) public milestones;
    mapping(address => Researcher) public researchers;
    mapping(address => Funder) public funders;
    mapping(uint256 => ValidationRequest) public validationRequests;
    mapping(address => bool) public authorizedOracles;
    
    uint256 public nextMilestoneId = 1;
    uint256 public nextValidationId = 1;
    uint256 public platformFeePercent = 250; // 2.5% (basis points)
    uint256 public constant MAX_FEE = 1000; // Max 10%
    
    address public feeRecipient;
    address public aiOracle;
    
    // Thresholds for automated decisions
    uint8 public autoApprovalThreshold = 85;    // 85% confidence for auto-approval
    uint8 public humanReviewThreshold = 70;     // Below 70% requires human review
    
    // ============ Events ============
    
    event MilestoneCreated(
        uint256 indexed milestoneId,
        address indexed researcher,
        address indexed funder,
        uint256 amount,
        string description
    );
    
    event MilestoneSubmitted(
        uint256 indexed milestoneId,
        string ipfsHash,
        uint256 submittedAt
    );
    
    event ValidationRequested(
        uint256 indexed validationId,
        uint256 indexed milestoneId,
        string contentHash
    );
    
    event MilestoneValidated(
        uint256 indexed milestoneId,
        bool approved,
        uint8 confidenceScore,
        string validationReport
    );
    
    event PaymentProcessed(
        uint256 indexed milestoneId,
        address indexed researcher,
        uint256 amount,
        uint256 platformFee
    );
    
    event DisputeRaised(
        uint256 indexed milestoneId,
        address indexed initiator,
        string reason
    );
    
    // ============ Modifiers ============
    
    modifier onlyOracle() {
        require(authorizedOracles[msg.sender], "Not authorized oracle");
        _;
    }
    
    modifier onlyResearcher(uint256 milestoneId) {
        require(milestones[milestoneId].researcher == msg.sender, "Not milestone researcher");
        _;
    }
    
    modifier onlyFunder(uint256 milestoneId) {
        require(milestones[milestoneId].funder == msg.sender, "Not milestone funder");
        _;
    }
    
    modifier milestoneExists(uint256 milestoneId) {
        require(milestones[milestoneId].id != 0, "Milestone does not exist");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(address _feeRecipient, address _aiOracle) Ownable(msg.sender) {
        feeRecipient = _feeRecipient;
        aiOracle = _aiOracle;
        authorizedOracles[_aiOracle] = true;
    }
    
    // ============ Core Functions ============
    
    /**
     * @dev Create a new milestone with escrow funding
     */
    function createMilestone(
        address _researcher,
        string memory _description,
        string memory _ipfsHash,
        uint256 _deadline
    ) external payable whenNotPaused nonReentrant {
        require(msg.value > 0, "Must fund milestone");
        require(_researcher != address(0), "Invalid researcher");
        require(_researcher != msg.sender, "Cannot fund yourself");
        require(_deadline > block.timestamp, "Invalid deadline");
        require(bytes(_description).length > 0, "Description required");
        
        uint256 milestoneId = nextMilestoneId++;
        
        milestones[milestoneId] = Milestone({
            id: milestoneId,
            researcher: _researcher,
            funder: msg.sender,
            amount: msg.value,
            ipfsHash: _ipfsHash,
            description: _description,
            deadline: _deadline,
            status: MilestoneStatus.CREATED,
            submittedAt: 0,
            validatedAt: 0,
            confidenceScore: 0,
            validationReport: ""
        });
        
        // Update funder profile
        if (funders[msg.sender].wallet == address(0)) {
            funders[msg.sender] = Funder({
                wallet: msg.sender,
                profile: "",
                totalFunded: msg.value,
                activeMilestones: 1,
                isInstitution: false
            });
        } else {
            funders[msg.sender].totalFunded += msg.value;
            funders[msg.sender].activeMilestones++;
        }
        
        emit MilestoneCreated(milestoneId, _researcher, msg.sender, msg.value, _description);
    }
    
    /**
     * @dev Researcher submits deliverables for validation
     */
    function submitMilestone(
        uint256 _milestoneId,
        string memory _ipfsHash
    ) external onlyResearcher(_milestoneId) milestoneExists(_milestoneId) whenNotPaused {
        Milestone storage milestone = milestones[_milestoneId];
        require(milestone.status == MilestoneStatus.CREATED, "Invalid milestone status");
        require(block.timestamp <= milestone.deadline, "Deadline passed");
        require(bytes(_ipfsHash).length > 0, "IPFS hash required");
        
        milestone.ipfsHash = _ipfsHash;
        milestone.status = MilestoneStatus.SUBMITTED;
        milestone.submittedAt = block.timestamp;
        
        // Request AI validation
        uint256 validationId = nextValidationId++;
        validationRequests[validationId] = ValidationRequest({
            milestoneId: _milestoneId,
            contentHash: _ipfsHash,
            requestedAt: block.timestamp,
            isProcessed: false
        });
        
        milestone.status = MilestoneStatus.AI_VALIDATING;
        
        emit MilestoneSubmitted(_milestoneId, _ipfsHash, block.timestamp);
        emit ValidationRequested(validationId, _milestoneId, _ipfsHash);
    }
    
    /**
     * @dev AI Oracle validates milestone and processes payment if confident enough
     */
    function validateMilestone(
        uint256 _milestoneId,
        bool _approved,
        uint8 _confidenceScore,
        string memory _validationReport
    ) external onlyOracle milestoneExists(_milestoneId) whenNotPaused {
        Milestone storage milestone = milestones[_milestoneId];
        require(milestone.status == MilestoneStatus.AI_VALIDATING, "Not awaiting validation");
        require(_confidenceScore <= 100, "Invalid confidence score");
        
        milestone.confidenceScore = _confidenceScore;
        milestone.validationReport = _validationReport;
        milestone.validatedAt = block.timestamp;
        
        if (_approved && _confidenceScore >= autoApprovalThreshold) {
            // High confidence approval - process payment immediately
            milestone.status = MilestoneStatus.APPROVED;
            _processPayment(_milestoneId);
        } else if (_confidenceScore >= humanReviewThreshold) {
            // Medium confidence - require human review
            milestone.status = MilestoneStatus.HUMAN_REVIEW;
        } else {
            // Low confidence - likely rejection, but allow dispute
            milestone.status = MilestoneStatus.DISPUTED;
        }
        
        emit MilestoneValidated(_milestoneId, _approved, _confidenceScore, _validationReport);
    }
    
    /**
     * @dev Process payment to researcher (internal function)
     */
    function _processPayment(uint256 _milestoneId) internal {
        Milestone storage milestone = milestones[_milestoneId];
        require(milestone.status == MilestoneStatus.APPROVED, "Not approved for payment");
        
        uint256 platformFee = (milestone.amount * platformFeePercent) / 10000;
        uint256 researcherAmount = milestone.amount - platformFee;
        
        milestone.status = MilestoneStatus.PAID;
        
        // Update researcher profile
        if (researchers[milestone.researcher].wallet == address(0)) {
            researchers[milestone.researcher] = Researcher({
                wallet: milestone.researcher,
                profile: "",
                completedMilestones: 1,
                totalEarned: researcherAmount,
                reputationScore: 100, // Starting reputation
                isVerified: false
            });
        } else {
            researchers[milestone.researcher].completedMilestones++;
            researchers[milestone.researcher].totalEarned += researcherAmount;
            // Increase reputation based on successful completion
            uint256 newReputation = researchers[milestone.researcher].reputationScore + 10;
            researchers[milestone.researcher].reputationScore = newReputation > 1000 ? 1000 : newReputation;
        }
        
        // Update funder profile
        funders[milestone.funder].activeMilestones--;
        
        // Transfer payments
        payable(milestone.researcher).transfer(researcherAmount);
        payable(feeRecipient).transfer(platformFee);
        
        emit PaymentProcessed(_milestoneId, milestone.researcher, researcherAmount, platformFee);
    }
    
    /**
     * @dev Manual approval by funder for disputed or human review cases
     */
    function approveMilestone(uint256 _milestoneId) 
        external 
        onlyFunder(_milestoneId) 
        milestoneExists(_milestoneId) 
        whenNotPaused 
    {
        Milestone storage milestone = milestones[_milestoneId];
        require(
            milestone.status == MilestoneStatus.HUMAN_REVIEW || 
            milestone.status == MilestoneStatus.DISPUTED,
            "Cannot manually approve"
        );
        
        milestone.status = MilestoneStatus.APPROVED;
        _processPayment(_milestoneId);
    }
    
    /**
     * @dev Raise dispute for a milestone
     */
    function raiseDispute(uint256 _milestoneId, string memory _reason) 
        external 
        milestoneExists(_milestoneId) 
        whenNotPaused 
    {
        require(
            msg.sender == milestones[_milestoneId].researcher ||
            msg.sender == milestones[_milestoneId].funder,
            "Not authorized to dispute"
        );
        
        Milestone storage milestone = milestones[_milestoneId];
        require(
            milestone.status == MilestoneStatus.HUMAN_REVIEW ||
            milestone.status == MilestoneStatus.APPROVED,
            "Cannot dispute at this stage"
        );
        
        milestone.status = MilestoneStatus.DISPUTED;
        emit DisputeRaised(_milestoneId, msg.sender, _reason);
    }
    
    /**
     * @dev Cancel milestone and refund (only before submission)
     */
    function cancelMilestone(uint256 _milestoneId) 
        external 
        onlyFunder(_milestoneId) 
        milestoneExists(_milestoneId) 
        whenNotPaused 
        nonReentrant 
    {
        Milestone storage milestone = milestones[_milestoneId];
        require(milestone.status == MilestoneStatus.CREATED, "Cannot cancel after submission");
        
        uint256 refundAmount = milestone.amount;
        milestone.status = MilestoneStatus.CANCELLED;
        milestone.amount = 0;
        
        // Update funder profile
        funders[msg.sender].activeMilestones--;
        
        payable(msg.sender).transfer(refundAmount);
    }
    
    // ============ Admin Functions ============
    
    function setOracle(address _oracle, bool _authorized) external onlyOwner {
        authorizedOracles[_oracle] = _authorized;
    }
    
    function setPlatformFee(uint256 _feePercent) external onlyOwner {
        require(_feePercent <= MAX_FEE, "Fee too high");
        platformFeePercent = _feePercent;
    }
    
    function setThresholds(uint8 _autoApproval, uint8 _humanReview) external onlyOwner {
        require(_autoApproval > _humanReview, "Invalid thresholds");
        require(_humanReview > 0, "Human review threshold too low");
        autoApprovalThreshold = _autoApproval;
        humanReviewThreshold = _humanReview;
    }
    
    function setFeeRecipient(address _feeRecipient) external onlyOwner {
        require(_feeRecipient != address(0), "Invalid address");
        feeRecipient = _feeRecipient;
    }
    
    function pause() external onlyOwner {
        _pause();
    }
    
    function unpause() external onlyOwner {
        _unpause();
    }
    
    // ============ View Functions ============
    
    function getMilestone(uint256 _milestoneId) external view returns (Milestone memory) {
        return milestones[_milestoneId];
    }
    
    function getResearcherStats(address _researcher) external view returns (Researcher memory) {
        return researchers[_researcher];
    }
    
    function getFunderStats(address _funder) external view returns (Funder memory) {
        return funders[_funder];
    }
    
    function getPendingValidations() external view returns (uint256[] memory) {
        // This is a simplified version - in production you'd want more efficient tracking
        uint256[] memory pending = new uint256[](nextMilestoneId - 1);
        uint256 count = 0;
        
        for (uint256 i = 1; i < nextMilestoneId; i++) {
            if (milestones[i].status == MilestoneStatus.AI_VALIDATING) {
                pending[count] = i;
                count++;
            }
        }
        
        // Resize array to actual count
        uint256[] memory result = new uint256[](count);
        for (uint256 j = 0; j < count; j++) {
            result[j] = pending[j];
        }
        
        return result;
    }
    
    // ============ Emergency Functions ============
    
    /**
     * @dev Emergency function to rescue funds if needed
     */
    function emergencyRefund(uint256 _milestoneId) external onlyOwner {
        Milestone storage milestone = milestones[_milestoneId];
        require(milestone.status != MilestoneStatus.PAID, "Already paid");
        require(milestone.status != MilestoneStatus.CANCELLED, "Already cancelled");
        
        uint256 refundAmount = milestone.amount;
        milestone.status = MilestoneStatus.CANCELLED;
        milestone.amount = 0;
        
        payable(milestone.funder).transfer(refundAmount);
    }
    
    /**
     * @dev Get contract balance
     */
    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }
}