package com.fcap.model;

import java.time.LocalDateTime;
import java.util.Objects;

/**
 * Represents an AML alert raised by the risk scoring or pattern detection engine.
 *
 * <p>Alerts are the primary work items for AML investigators. Each alert captures
 * the triggering entity, alert classification, risk score, and current workflow
 * status.
 */
public class Alert {

    /**
     * Classifies the type of suspicious activity that triggered the alert.
     */
    public enum AlertType {
        STRUCTURING,
        LAYERING,
        RAPID_MOVEMENT,
        HIGH_VALUE
    }

    /**
     * Lifecycle status of the alert within the investigation workflow.
     */
    public enum AlertStatus {
        OPEN,
        UNDER_REVIEW,
        CLOSED,
        ESCALATED
    }

    private String alertId;
    private String entityId;
    private AlertType alertType;
    private Double riskScore;
    private AlertStatus status;
    private LocalDateTime createdAt;
    private String description;

    // -------------------------------------------------------------------------
    // Constructors
    // -------------------------------------------------------------------------

    public Alert() {}

    private Alert(Builder builder) {
        this.alertId     = builder.alertId;
        this.entityId    = builder.entityId;
        this.alertType   = builder.alertType;
        this.riskScore   = builder.riskScore;
        this.status      = builder.status;
        this.createdAt   = builder.createdAt;
        this.description = builder.description;
    }

    // -------------------------------------------------------------------------
    // Builder
    // -------------------------------------------------------------------------

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String alertId;
        private String entityId;
        private AlertType alertType;
        private Double riskScore;
        private AlertStatus status = AlertStatus.OPEN;
        private LocalDateTime createdAt = LocalDateTime.now();
        private String description;

        private Builder() {}

        public Builder alertId(String alertId) {
            this.alertId = alertId;
            return this;
        }

        public Builder entityId(String entityId) {
            this.entityId = entityId;
            return this;
        }

        public Builder alertType(AlertType alertType) {
            this.alertType = alertType;
            return this;
        }

        public Builder riskScore(Double riskScore) {
            this.riskScore = riskScore;
            return this;
        }

        public Builder status(AlertStatus status) {
            this.status = status;
            return this;
        }

        public Builder createdAt(LocalDateTime createdAt) {
            this.createdAt = createdAt;
            return this;
        }

        public Builder description(String description) {
            this.description = description;
            return this;
        }

        public Alert build() {
            Objects.requireNonNull(alertId, "alertId must not be null");
            Objects.requireNonNull(entityId, "entityId must not be null");
            Objects.requireNonNull(alertType, "alertType must not be null");
            return new Alert(this);
        }
    }

    // -------------------------------------------------------------------------
    // Getters / Setters
    // -------------------------------------------------------------------------

    public String getAlertId() { return alertId; }
    public void setAlertId(String alertId) { this.alertId = alertId; }

    public String getEntityId() { return entityId; }
    public void setEntityId(String entityId) { this.entityId = entityId; }

    public AlertType getAlertType() { return alertType; }
    public void setAlertType(AlertType alertType) { this.alertType = alertType; }

    public Double getRiskScore() { return riskScore; }
    public void setRiskScore(Double riskScore) { this.riskScore = riskScore; }

    public AlertStatus getStatus() { return status; }
    public void setStatus(AlertStatus status) { this.status = status; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    // -------------------------------------------------------------------------
    // Object overrides
    // -------------------------------------------------------------------------

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Alert)) return false;
        Alert alert = (Alert) o;
        return Objects.equals(alertId, alert.alertId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(alertId);
    }

    @Override
    public String toString() {
        return "Alert{" +
                "alertId='" + alertId + '\'' +
                ", entityId='" + entityId + '\'' +
                ", alertType=" + alertType +
                ", riskScore=" + riskScore +
                ", status=" + status +
                ", createdAt=" + createdAt +
                ", description='" + description + '\'' +
                '}';
    }
}
