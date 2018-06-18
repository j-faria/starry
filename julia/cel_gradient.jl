# Trying out derivatives of cel_bulirsch with respect to
# k_c, p, a, b:
include("cel_bulirsch.jl")

using ForwardDiff

dcel_dn = m -> ForwardDiff.derivative(cel_bulirsch,m)

function cel_grad(kc::T,p::T,a::T,b::T) where {T <: Real}
  # Computes the derivative of cel(k_c,p,a,b) with respect to (k_c,p,a,b)
  # Create a vector for use with ForwardDiff
  x=[kc,p,a,b]
  # Now, define a wrapper of cel_bulirsch for use with ForwardDiff:
  function diff_cel(x::Array{T,1}) where {T <: Real}
  # x should be a four-element vector with values [kc,p,a,b]
  kc,p,a,b = x
  return cel_bulirsch(1.0-kc*kc,p,a,b)
  end

  # Set up a type to store s_n and it's Jacobian with respect to x:
  out = DiffResults.GradientResult(x)
  # Compute the Jacobian (and value):
  out = ForwardDiff.gradient!(out,diff_cel,x)
  # Place the value in the cel_b vector:
  cel_b = DiffResults.value(out)
  # And, place the Jacobian in an array:
  cel_gradient= DiffResults.gradient(out)
return cel_b,cel_gradient
end

kc = rand(); p = rand(); a=rand(); b= rand()
cel_b,cel_gradient= cel_grad(kc,p,a,b)

# Now, compute the gradients analytically:
kc2 = kc*kc
dcel_dkc = -kc/(p-kc2)*(cel_bulirsch(1-kc*kc,kc2,a,b)-cel_b)

dcel_dp = (2*p*b-p*a-b)/(2*p*(1-p))*cel_bulirsch(1-kc*kc,p,zero(p),one(p))+
  (b-a*p)/(2*p*(1-p)*(p-kc2))*cel_bulirsch(1-kc*kc,one(p),one(p),kc2) -
  (b-a*p)/(2*(1-p)*(p-kc2))*cel_bulirsch(1-kc*kc,p,one(p),one(p))

dcel_da = cel_bulirsch(1-kc*kc,p,one(p),zero(p))
dcel_db = cel_bulirsch(1-kc*kc,p,zero(p),one(p))
epsilon = 1e-15
println("d cel/d kc: ",dcel_dkc," ",cel_gradient[1]," ",
  convert(Float64,(cel_bulirsch(big(1)-(big(kc)+big(epsilon))^2,big(p),big(a),big(b))
  -cel_bulirsch(big(1)-(big(kc)-big(epsilon))^2,big(p),big(a),big(b)))/(2*big(epsilon))))
println("d cel/d p: ",dcel_dp," ",cel_gradient[2]," ",
  convert(Float64,(cel_bulirsch(big(1)-big(kc)^2,big(p)+big(epsilon),big(a),big(b))
  -cel_bulirsch(big(1)-big(kc)^2,big(p)-big(epsilon),big(a),big(b)))/(2*big(epsilon))))
println("d cel/d a: ",dcel_da," ",cel_gradient[3]," ",
  convert(Float64,(cel_bulirsch(big(1)-big(kc)^2,big(p),big(a)+big(epsilon),big(b))
  -cel_bulirsch(big(1)-big(kc)^2,big(p),big(a)-big(epsilon),big(b)))/(2*big(epsilon))))
println("d cel/d b: ",dcel_db," ",cel_gradient[4]," ",
  convert(Float64,(cel_bulirsch(big(1)-big(kc)^2,big(p),big(a),big(b)+big(epsilon))
  -cel_bulirsch(big(1)-big(kc)^2,big(p),big(a),big(b)-big(epsilon)))/(2*big(epsilon))))